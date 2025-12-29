"""
API routes for data issue detection and fix suggestions.

These endpoints provide functionality for:
- Detecting data quality issues in datasets
- Previewing suggested fixes
- Applying fixes to resolve issues
- Batch fix operations
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from beanie import PydanticObjectId
from datetime import datetime, timezone
import logging
import time

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.models.data_issue import (
    DataIssueRecord,
    DataIssue,
    IssueSeverity,
)
from app.schemas.data_issue import (
    IssueDetectionRequest,
    IssueDetectionResponse,
    FixPreviewRequest,
    FixPreviewResponse,
    FixApplicationRequest,
    FixApplicationResponse,
    BatchFixRequest,
    BatchFixResponse,
    BatchFixResult,
    DataIssueResponse,
    SuggestedFixResponse,
    DetectionSummaryResponse,
    IssueHistoryResponse,
    IssueHistoryListResponse,
)
from app.services.data_issue_detection_service import DataIssueDetectionService
from app.services.fix_suggestion_engine import FixSuggestionEngine
from app.services.transformation_engine.data_utils import (
    get_dataframe_from_s3,
    upload_dataframe_to_s3,
)
from app.services.exceptions import OperationError, ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)


def _convert_issue_to_response(issue: DataIssue) -> DataIssueResponse:
    """Convert DataIssue model to response schema."""
    return DataIssueResponse(
        issue_id=issue.issue_id,
        issue_type=issue.issue_type.value,
        severity=issue.severity.value,
        affected_column=issue.affected_column,
        affected_columns=issue.affected_columns,
        affected_rows=issue.affected_rows,
        affected_percentage=issue.affected_percentage,
        description=issue.description,
        impact=issue.impact,
        suggested_fixes=[
            SuggestedFixResponse(
                fix_id=fix.fix_id,
                transformation_type=fix.transformation_type,
                parameters=fix.parameters,
                explanation=fix.explanation,
                ai_generated=fix.ai_generated,
                confidence_score=fix.confidence_score,
                estimated_rows_affected=fix.estimated_rows_affected,
                estimated_data_loss=fix.estimated_data_loss,
                is_safe=fix.is_safe,
            )
            for fix in issue.suggested_fixes
        ],
        ai_generated=issue.ai_generated,
        ai_explanation=issue.ai_explanation,
        detected_at=issue.detected_at,
        example_values=issue.example_values,
    )


@router.post("/detect", response_model=IssueDetectionResponse)
async def detect_issues(
    request: IssueDetectionRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Detect data quality issues in a dataset.

    This endpoint analyzes the dataset for:
    - Missing values
    - Duplicates
    - Outliers
    - Format inconsistencies
    - Type mismatches
    - AI-detected semantic issues (optional)

    Returns a list of detected issues with suggested fixes.
    """
    start_time = time.time()

    try:
        # Get the dataset
        try:
            dataset_oid = PydanticObjectId(request.dataset_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid dataset ID format")

        user_data = await UserData.find_one(
            UserData.id == dataset_oid,
            UserData.user_id == current_user_id,
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Load data from S3
        file_path = user_data.file_path or user_data.s3_url
        if not file_path:
            raise HTTPException(status_code=400, detail="Dataset has no associated file")

        df = await get_dataframe_from_s3(file_path)

        # Get column types from schema
        column_types = {}
        if user_data.data_schema:
            column_types = {
                field.field_name: field.data_type
                for field in user_data.data_schema
            }

        # Run detection
        detection_service = DataIssueDetectionService()
        issues, summary = await detection_service.detect_issues(
            df=df,
            column_types=column_types,
            options=request.options,
            include_ai_analysis=request.options.include_ai_analysis,
        )

        # Store detection results
        record = await detection_service.store_detection_results(
            dataset_id=request.dataset_id,
            user_id=current_user_id,
            issues=issues,
            summary=summary,
            options=request.options,
        )

        detection_time_ms = int((time.time() - start_time) * 1000)

        return IssueDetectionResponse(
            success=True,
            dataset_id=request.dataset_id,
            issues=[_convert_issue_to_response(issue) for issue in issues],
            summary=DetectionSummaryResponse(
                total_issues=summary.total_issues,
                critical_count=summary.critical_count,
                high_count=summary.high_count,
                medium_count=summary.medium_count,
                low_count=summary.low_count,
                ai_detected_count=summary.ai_detected_count,
                auto_fixable_count=summary.auto_fixable_count,
                detection_time_ms=detection_time_ms,
                columns_analyzed=summary.columns_analyzed,
                rows_analyzed=summary.rows_analyzed,
            ),
            record_id=str(record.id),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Issue detection failed: {str(e)}")
        return IssueDetectionResponse(
            success=False,
            dataset_id=request.dataset_id,
            error=str(e),
        )


@router.get("/{dataset_id}/issues", response_model=IssueDetectionResponse)
async def get_dataset_issues(
    dataset_id: str,
    include_ai: bool = Query(True, description="Include AI-detected issues"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get the most recent detected issues for a dataset.

    Returns cached detection results if available.
    """
    try:
        # Get latest detection record
        record = await DataIssueRecord.find_one(
            DataIssueRecord.dataset_id == dataset_id,
            DataIssueRecord.user_id == current_user_id,
            sort=[("detected_at", -1)]
        )

        if not record:
            raise HTTPException(
                status_code=404,
                detail="No issue detection results found. Run detection first."
            )

        # Filter issues if requested
        issues = record.issues
        if severity:
            try:
                sev = IssueSeverity(severity)
                issues = [i for i in issues if i.severity == sev]
            except ValueError:
                pass

        if not include_ai:
            issues = [i for i in issues if not i.ai_generated]

        return IssueDetectionResponse(
            success=True,
            dataset_id=dataset_id,
            issues=[_convert_issue_to_response(issue) for issue in issues],
            summary=DetectionSummaryResponse(
                total_issues=record.summary.total_issues,
                critical_count=record.summary.critical_count,
                high_count=record.summary.high_count,
                medium_count=record.summary.medium_count,
                low_count=record.summary.low_count,
                ai_detected_count=record.summary.ai_detected_count,
                auto_fixable_count=record.summary.auto_fixable_count,
                detection_time_ms=record.summary.detection_time_ms,
                columns_analyzed=record.summary.columns_analyzed,
                rows_analyzed=record.summary.rows_analyzed,
            ),
            record_id=str(record.id),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get issues failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview-fix", response_model=FixPreviewResponse)
async def preview_fix(
    request: FixPreviewRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Preview a suggested fix before applying it.

    Shows before/after data comparison and estimated impact.
    """
    try:
        # Get the dataset
        try:
            dataset_oid = PydanticObjectId(request.dataset_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid dataset ID format")

        user_data = await UserData.find_one(
            UserData.id == dataset_oid,
            UserData.user_id == current_user_id,
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get the issue record
        record = await DataIssueRecord.find_one(
            DataIssueRecord.dataset_id == request.dataset_id,
            DataIssueRecord.user_id == current_user_id,
            sort=[("detected_at", -1)]
        )

        if not record:
            raise HTTPException(status_code=404, detail="No issues found for this dataset")

        # Find the specific issue
        issue = None
        for i in record.issues:
            if i.issue_id == request.issue_id:
                issue = i
                break

        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue {request.issue_id} not found")

        # Find the fix to preview
        fix = None
        if request.fix_id:
            for f in issue.suggested_fixes:
                if f.fix_id == request.fix_id:
                    fix = f
                    break
        elif issue.suggested_fixes:
            fix = issue.suggested_fixes[0]

        if not fix:
            raise HTTPException(status_code=404, detail="No fix found to preview")

        # Load data
        file_path = user_data.file_path or user_data.s3_url
        df = await get_dataframe_from_s3(file_path)

        # Preview the fix
        engine = FixSuggestionEngine()
        preview_result = engine.preview_fix(
            df=df,
            issue=issue,
            fix=fix,
            n_rows=request.preview_rows,
        )

        if not preview_result.get("success"):
            return FixPreviewResponse(
                success=False,
                issue_id=request.issue_id,
                fix_id=fix.fix_id,
                error=preview_result.get("error", "Preview failed"),
            )

        return FixPreviewResponse(
            success=True,
            issue_id=request.issue_id,
            fix_id=fix.fix_id,
            preview_data_before=preview_result.get("preview_data_before"),
            preview_data_after=preview_result.get("preview_data_after"),
            affected_rows=preview_result.get("affected_rows", 0),
            affected_columns=preview_result.get("affected_columns", []),
            estimated_data_loss=fix.estimated_data_loss,
            warnings=preview_result.get("warnings", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview fix failed: {str(e)}")
        return FixPreviewResponse(
            success=False,
            issue_id=request.issue_id,
            fix_id=request.fix_id or "",
            error=str(e),
        )


@router.post("/apply-fix", response_model=FixApplicationResponse)
async def apply_fix(
    request: FixApplicationRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Apply a suggested fix to the dataset.

    Can optionally save as a new dataset version.
    """
    start_time = time.time()

    try:
        # Get the dataset
        try:
            dataset_oid = PydanticObjectId(request.dataset_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid dataset ID format")

        user_data = await UserData.find_one(
            UserData.id == dataset_oid,
            UserData.user_id == current_user_id,
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get the issue record
        record = await DataIssueRecord.find_one(
            DataIssueRecord.dataset_id == request.dataset_id,
            DataIssueRecord.user_id == current_user_id,
            sort=[("detected_at", -1)]
        )

        if not record:
            raise HTTPException(status_code=404, detail="No issues found for this dataset")

        # Find the issue
        issue = None
        for i in record.issues:
            if i.issue_id == request.issue_id:
                issue = i
                break

        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue {request.issue_id} not found")

        # Find the fix
        fix = None
        if request.fix_id:
            for f in issue.suggested_fixes:
                if f.fix_id == request.fix_id:
                    fix = f
                    break
        elif issue.suggested_fixes:
            fix = issue.suggested_fixes[0]

        if not fix:
            raise HTTPException(status_code=404, detail="No fix found to apply")

        # If preview mode, just return preview
        if request.preview_mode:
            file_path = user_data.file_path or user_data.s3_url
            df = await get_dataframe_from_s3(file_path)
            engine = FixSuggestionEngine()
            preview_result = engine.preview_fix(df, issue, fix, n_rows=100)

            return FixApplicationResponse(
                success=True,
                dataset_id=request.dataset_id,
                issue_id=request.issue_id,
                fix_id=fix.fix_id,
                affected_rows=preview_result.get("affected_rows", 0),
                affected_columns=preview_result.get("affected_columns", []),
                execution_time_ms=int((time.time() - start_time) * 1000),
                warnings=["Preview mode - fix not applied"],
            )

        # Load data and apply fix
        file_path = user_data.file_path or user_data.s3_url
        df = await get_dataframe_from_s3(file_path)

        engine = FixSuggestionEngine()
        transformed_df, applied_fix = engine.apply_fix(
            df=df,
            issue=issue,
            fix=fix,
            user_id=current_user_id,
        )

        # Save transformed data
        timestamp = datetime.now(timezone.utc).timestamp()
        new_file_path = await upload_dataframe_to_s3(
            transformed_df,
            f"transformed/{current_user_id}/{request.dataset_id}_{timestamp}.parquet"
        )

        # Update dataset record
        user_data.file_path = new_file_path
        user_data.updated_at = datetime.now(timezone.utc)
        user_data.num_rows = len(transformed_df)
        await user_data.save()

        # Update issue record
        record.add_applied_fix(applied_fix)
        record.mark_issue_fixed(request.issue_id)
        await record.save()

        execution_time_ms = int((time.time() - start_time) * 1000)

        return FixApplicationResponse(
            success=True,
            dataset_id=request.dataset_id,
            issue_id=request.issue_id,
            fix_id=fix.fix_id,
            transformation_id=applied_fix.fix_id,
            affected_rows=applied_fix.rows_affected,
            affected_columns=fix.parameters.get("columns", []),
            execution_time_ms=execution_time_ms,
            new_version_id=new_file_path if request.save_as_new_version else None,
        )

    except HTTPException:
        raise
    except (ValidationError, OperationError) as e:
        logger.error(f"Apply fix failed: {str(e)}")
        return FixApplicationResponse(
            success=False,
            dataset_id=request.dataset_id,
            issue_id=request.issue_id,
            fix_id=request.fix_id or "",
            execution_time_ms=int((time.time() - start_time) * 1000),
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Apply fix failed: {str(e)}")
        return FixApplicationResponse(
            success=False,
            dataset_id=request.dataset_id,
            issue_id=request.issue_id,
            fix_id=request.fix_id or "",
            execution_time_ms=int((time.time() - start_time) * 1000),
            error=str(e),
        )


@router.post("/batch-fix", response_model=BatchFixResponse)
async def batch_apply_fixes(
    request: BatchFixRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Apply multiple fixes in batch.

    Can optionally apply only safe fixes automatically.
    """
    start_time = time.time()

    try:
        # Get the dataset
        try:
            dataset_oid = PydanticObjectId(request.dataset_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid dataset ID format")

        user_data = await UserData.find_one(
            UserData.id == dataset_oid,
            UserData.user_id == current_user_id,
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get the issue record
        record = await DataIssueRecord.find_one(
            DataIssueRecord.dataset_id == request.dataset_id,
            DataIssueRecord.user_id == current_user_id,
            sort=[("detected_at", -1)]
        )

        if not record:
            raise HTTPException(status_code=404, detail="No issues found for this dataset")

        # Get issues to fix
        issues_to_fix = [
            i for i in record.issues
            if i.issue_id in request.issue_ids
        ]

        if not issues_to_fix:
            raise HTTPException(status_code=400, detail="No matching issues found")

        # Preview mode check
        if request.preview_mode:
            results = []
            for issue in issues_to_fix:
                if issue.suggested_fixes:
                    fix = issue.suggested_fixes[0]
                    if not request.auto_apply_safe or fix.is_safe:
                        results.append(BatchFixResult(
                            issue_id=issue.issue_id,
                            fix_id=fix.fix_id,
                            success=True,
                            affected_rows=fix.estimated_rows_affected,
                        ))

            return BatchFixResponse(
                success=True,
                dataset_id=request.dataset_id,
                total_fixes=len(results),
                successful_fixes=len(results),
                failed_fixes=0,
                results=results,
                execution_time_ms=int((time.time() - start_time) * 1000),
                warnings=["Preview mode - fixes not applied"],
            )

        # Load data
        file_path = user_data.file_path or user_data.s3_url
        df = await get_dataframe_from_s3(file_path)

        # Apply fixes in batch
        engine = FixSuggestionEngine()
        transformed_df, applied_fixes, errors = await engine.apply_batch_fixes(
            df=df,
            issues=issues_to_fix,
            user_id=current_user_id,
            auto_apply_safe_only=request.auto_apply_safe,
            stop_on_error=request.stop_on_error,
        )

        # Build results
        results = []
        total_rows_affected = 0

        for applied in applied_fixes:
            results.append(BatchFixResult(
                issue_id=applied.issue_id,
                fix_id=applied.fix_id,
                success=applied.success,
                affected_rows=applied.rows_affected,
                error=applied.error_message,
            ))
            total_rows_affected += applied.rows_affected

        # Add error entries for failed fixes
        successful_ids = {a.issue_id for a in applied_fixes}
        for error in errors:
            # Extract issue_id from error message if possible
            results.append(BatchFixResult(
                issue_id="",  # Unknown if error doesn't contain issue_id
                fix_id="",
                success=False,
                error=error,
            ))

        # Save transformed data if any fixes were applied
        new_version_id = None
        if applied_fixes:
            timestamp = datetime.now(timezone.utc).timestamp()
            new_file_path = await upload_dataframe_to_s3(
                transformed_df,
                f"transformed/{current_user_id}/{request.dataset_id}_{timestamp}.parquet"
            )

            # Update dataset
            user_data.file_path = new_file_path
            user_data.updated_at = datetime.now(timezone.utc)
            user_data.num_rows = len(transformed_df)
            await user_data.save()

            # Update issue record
            for applied in applied_fixes:
                record.add_applied_fix(applied)
                record.mark_issue_fixed(applied.issue_id)
            await record.save()

            new_version_id = new_file_path

        execution_time_ms = int((time.time() - start_time) * 1000)

        return BatchFixResponse(
            success=len(errors) == 0,
            dataset_id=request.dataset_id,
            total_fixes=len(results),
            successful_fixes=len(applied_fixes),
            failed_fixes=len(errors),
            results=results,
            total_rows_affected=total_rows_affected,
            execution_time_ms=execution_time_ms,
            new_version_id=new_version_id,
            warnings=errors if errors else [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch fix failed: {str(e)}")
        return BatchFixResponse(
            success=False,
            dataset_id=request.dataset_id,
            execution_time_ms=int((time.time() - start_time) * 1000),
            error=str(e),
        )


@router.get("/{dataset_id}/history", response_model=IssueHistoryListResponse)
async def get_issue_history(
    dataset_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get history of issue detections for a dataset.
    """
    try:
        # Count total records
        total = await DataIssueRecord.find(
            DataIssueRecord.dataset_id == dataset_id,
            DataIssueRecord.user_id == current_user_id,
        ).count()

        # Get paginated records
        skip = (page - 1) * per_page
        records = await DataIssueRecord.find(
            DataIssueRecord.dataset_id == dataset_id,
            DataIssueRecord.user_id == current_user_id,
        ).sort(-DataIssueRecord.detected_at).skip(skip).limit(per_page).to_list()

        return IssueHistoryListResponse(
            records=[
                IssueHistoryResponse(
                    record_id=str(r.id),
                    dataset_id=r.dataset_id,
                    detected_at=r.detected_at,
                    summary=DetectionSummaryResponse(
                        total_issues=r.summary.total_issues,
                        critical_count=r.summary.critical_count,
                        high_count=r.summary.high_count,
                        medium_count=r.summary.medium_count,
                        low_count=r.summary.low_count,
                        ai_detected_count=r.summary.ai_detected_count,
                        auto_fixable_count=r.summary.auto_fixable_count,
                        detection_time_ms=r.summary.detection_time_ms,
                        columns_analyzed=r.summary.columns_analyzed,
                        rows_analyzed=r.summary.rows_analyzed,
                    ),
                    issues_count=len(r.issues),
                    applied_fixes_count=len(r.applied_fixes),
                )
                for r in records
            ],
            total=total,
            page=page,
            per_page=per_page,
        )

    except Exception as e:
        logger.error(f"Get history failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
