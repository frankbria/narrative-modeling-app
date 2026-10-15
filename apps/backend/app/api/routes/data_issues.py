"""
API routes for data issue detection and fix suggestions.

These endpoints provide functionality for:
- Detecting data quality issues in datasets
- Previewing suggested fixes
- Applying fixes to resolve issues
- Batch fix operations
"""

import logging
import time

import pandas as pd
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.nextauth_auth import get_current_user_id
from app.billing import enforcement
from app.middleware.error_handlers import internal_error_message
from app.middleware.upload_cleanup import discards_uploads_on_reported_failure
from app.models.data_issue import (
    AppliedFix,
    DataIssue,
    DataIssueRecord,
    IssueSeverity,
    SuggestedFix,
)
from app.models.user_data import UserData
from app.schemas.data_issue import (
    BatchFixRequest,
    BatchFixResponse,
    BatchFixResult,
    DataIssueResponse,
    DetectionSummaryResponse,
    FixApplicationRequest,
    FixApplicationResponse,
    FixPreviewRequest,
    FixPreviewResponse,
    IssueDetectionRequest,
    IssueDetectionResponse,
    IssueHistoryListResponse,
    IssueHistoryResponse,
    SuggestedFixResponse,
)
from app.services.data_issue_detection_service import DataIssueDetectionService
from app.services.dataset_link import (
    DATASET_BUSY,
    ensure_metadata_twin,
    holds_the_dataset,
)
from app.services.exceptions import NotFoundError, OperationError, ValidationError
from app.services.fix_suggestion_engine import FixSuggestionEngine
from app.services.transformation_engine.data_utils import get_dataframe_from_s3
from app.services.transformation_engine.transformation_engine import TransformationType
from app.services.transformation_service import TransformationService
from app.utils.s3 import downloadable_url

router = APIRouter()


def _download_url(user_data: UserData) -> str:
    """The dataset's current file as a URL the downloader accepts (#466).

    `file_path` is a raw key after an upload and a URL after a transformation; a
    dataset with nothing stored is the caller's 400, not a swallowed 200 `{success: false}`
    — every handler in this file reports it the same way.
    """
    try:
        return downloadable_url(user_data.file_path, user_data.s3_url)
    except ValueError:
        raise HTTPException(status_code=400, detail="Dataset has no associated file") from None


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
    http_request: Request,
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
    detection_service = DataIssueDetectionService()
    ai_reserved = False
    ai_used = False
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
        # ai_calls is reserved INSIDE the handler, only when the analyzer is asked for (#461):
        # a route dependency would 402 a tenant out of AI quota on a rule-based-only run.
        ai_reserved = bool(request.options.include_ai_analysis)
        if ai_reserved:
            await enforcement.reserve(http_request, current_user_id, "ai_calls")
        file_path = _download_url(user_data)

        df = await get_dataframe_from_s3(file_path)

        # Get column types from schema
        column_types: dict[str, str] = {}
        if user_data.data_schema:
            column_types = {
                field.field_name: field.data_type or ""
                for field in user_data.data_schema
            }

        # Run detection
        issues, summary = await detection_service.detect_issues(
            df=df,
            column_types=column_types,
            options=request.options,
            include_ai_analysis=request.options.include_ai_analysis,
        )
        ai_used = summary.ai_analysis_used  # decided here: a later failure must not refund a sent request

        # Store detection results
        record = await detection_service.store_detection_results(
            dataset_id=request.dataset_id,
            user_id=current_user_id,
            issues=issues,
            summary=summary,
            options=request.options,
        )
        if ai_reserved and not ai_used:
            await enforcement.release(http_request)  # no key, or the breaker's fallback: no paid call, no charge

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
                ai_analysis_used=summary.ai_analysis_used,
            ),
            record_id=str(record.id),
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Issue detection failed")
        # A request the analyzer DID send before a later step raised (inside the service or
        # here) stays charged: the service keeps the count outside the summary that never came back.
        ai_used = ai_used or getattr(detection_service, "last_ai_calls_made", 0) > 0
        if ai_reserved and not ai_used:
            # reported as 200 {success: false}, which the refund middleware never sees
            await enforcement.release(http_request)
        return IssueDetectionResponse(
            success=False,
            dataset_id=request.dataset_id,
            error=internal_error_message("Issue detection"),
        )


@router.get("/{dataset_id}/issues", response_model=IssueDetectionResponse)
async def get_dataset_issues(
    dataset_id: str,
    include_ai: bool = Query(True, description="Include AI-detected issues"),
    severity: str | None = Query(None, description="Filter by severity"),
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
                ai_analysis_used=record.summary.ai_analysis_used,
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
        raise HTTPException(status_code=500, detail="Internal server error") from e


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
        file_path = _download_url(user_data)
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
    except Exception:
        logger.exception("Preview fix failed")
        return FixPreviewResponse(
            success=False,
            issue_id=request.issue_id,
            fix_id=request.fix_id or "",
            error=internal_error_message("Preview fix"),
        )


async def _owned_upload(dataset_id: str, user_id: str) -> UserData:
    """The caller's upload; 400 for a malformed id, 404 for an unknown or foreign one."""
    try:
        dataset_oid = PydanticObjectId(dataset_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dataset ID format") from None
    user_data = await UserData.find_one(UserData.id == dataset_oid, UserData.user_id == user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return user_data


async def _latest_record(dataset_id: str, user_id: str) -> DataIssueRecord:
    record = await DataIssueRecord.find_one(
        DataIssueRecord.dataset_id == dataset_id,
        DataIssueRecord.user_id == user_id,
        sort=[("detected_at", -1)],
    )
    if not record:
        raise HTTPException(status_code=404, detail="No issues found for this dataset")
    return record


def _issue(record: DataIssueRecord, issue_id: str) -> DataIssue:
    issue = next((i for i in record.issues if i.issue_id == issue_id), None)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")
    return issue


def _fix(issue: DataIssue, fix_id: str | None) -> SuggestedFix:
    """The fix asked for, or the issue's first suggestion when none is named."""
    fixes = [f for f in issue.suggested_fixes if f.fix_id == fix_id] if fix_id else issue.suggested_fixes
    if not fixes:
        raise HTTPException(status_code=404, detail="No fix found to apply")
    return fixes[0]


def _fixed(issues: list[DataIssue]) -> str:
    """What the history lists for fixes (#923): each issue's own description."""
    noun = "data issue" if len(issues) == 1 else "data issues"
    return f"Fixed {noun}: " + "; ".join(issue.description for issue in issues)


def _columns_of(issues: list[DataIssue]) -> list[str]:
    return sorted({c for issue in issues for c in [issue.affected_column, *issue.affected_columns] if c})


async def _record_fixes(
    user_data: UserData, user_id: str, frames: tuple[pd.DataFrame, pd.DataFrame],
    issues: list[DataIssue], applied: list[AppliedFix],
) -> str:
    """Record the fixes as one history step and move the dataset to the result, so the
    history lists them and undo restores the step before (#923); the new file's URL.

    The history is keyed on the upload's `DatasetMetadata` twin, created here if the
    upload has none. A file a transformation cannot read is refused with its type named.
    """
    dataset = await ensure_metadata_twin(str(user_data.id), user_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return await TransformationService().record_edit(
        dataset, user_id, frames, kind=TransformationType.DATA_ISSUE_FIX.value,
        parameters={
            "columns": _columns_of(issues),
            "fixes": [a.model_dump(include={"issue_id", "fix_id", "transformation_type", "parameters"}) for a in applied],
        },
        description=_fixed(issues),
        rows_affected=sum(a.rows_affected for a in applied),
    )


def _fix_failed(request: FixApplicationRequest, start_time: float, error: str) -> FixApplicationResponse:
    return FixApplicationResponse(
        success=False,
        dataset_id=request.dataset_id,
        issue_id=request.issue_id,
        fix_id=request.fix_id or "",
        execution_time_ms=int((time.time() - start_time) * 1000),
        error=error,
    )


async def _previewed_fix(
    request: FixApplicationRequest, user_data: UserData, issue: DataIssue, fix: SuggestedFix, start_time: float
) -> FixApplicationResponse:
    df = await get_dataframe_from_s3(_download_url(user_data))
    preview_result = FixSuggestionEngine().preview_fix(df, issue, fix, n_rows=100)
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


async def _applied_fix(
    request: FixApplicationRequest, user_id: str, user_data: UserData, record: DataIssueRecord,
    issue: DataIssue, fix: SuggestedFix, start_time: float,
) -> FixApplicationResponse:
    df = await get_dataframe_from_s3(_download_url(user_data))
    transformed_df, applied_fix = FixSuggestionEngine().apply_fix(df=df, issue=issue, fix=fix, user_id=user_id)
    new_file_path = await _record_fixes(user_data, user_id, (df, transformed_df), [issue], [applied_fix])

    record.add_applied_fix(applied_fix)
    record.mark_issue_fixed(request.issue_id)
    await record.save()

    return FixApplicationResponse(
        success=True,
        dataset_id=request.dataset_id,
        issue_id=request.issue_id,
        fix_id=fix.fix_id,
        transformation_id=applied_fix.fix_id,
        affected_rows=applied_fix.rows_affected,
        affected_columns=fix.parameters.get("columns", []),
        execution_time_ms=int((time.time() - start_time) * 1000),
        new_version_id=new_file_path if request.save_as_new_version else None,
    )


@router.post("/apply-fix", response_model=FixApplicationResponse)
@discards_uploads_on_reported_failure
@holds_the_dataset(
    lambda kw: None if kw["request"].preview_mode else kw["request"].dataset_id,
    lambda kw: FixApplicationResponse(
        success=False, dataset_id=kw["request"].dataset_id, issue_id=kw["request"].issue_id,
        fix_id=kw["request"].fix_id or "", error=DATASET_BUSY,
    ),
)
async def apply_fix(
    request: FixApplicationRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Apply a suggested fix to the dataset, as one step of its transformation history.

    Can optionally save as a new dataset version.
    """
    start_time = time.time()
    try:
        user_data = await _owned_upload(request.dataset_id, current_user_id)
        record = await _latest_record(request.dataset_id, current_user_id)
        issue = _issue(record, request.issue_id)
        fix = _fix(issue, request.fix_id)
        if request.preview_mode:
            return await _previewed_fix(request, user_data, issue, fix, start_time)
        return await _applied_fix(request, current_user_id, user_data, record, issue, fix, start_time)
    except HTTPException:
        raise
    except (ValidationError, OperationError, NotFoundError) as e:
        logger.error(f"Apply fix failed: {str(e)}")
        return _fix_failed(request, start_time, str(e))
    except Exception:
        logger.exception("Apply fix failed")
        return _fix_failed(request, start_time, internal_error_message("Apply fix"))


def _issues_to_fix(record: DataIssueRecord, issue_ids: list[str]) -> list[DataIssue]:
    issues = [i for i in record.issues if i.issue_id in issue_ids]
    if not issues:
        raise HTTPException(status_code=400, detail="No matching issues found")
    return issues


def _first_fix(issue: DataIssue, safe_only: bool) -> SuggestedFix | None:
    """The fix a batch applies for the issue: its first suggestion, if it may."""
    if not issue.suggested_fixes:
        return None
    fix = issue.suggested_fixes[0]
    return None if safe_only and not fix.is_safe else fix


def _batch_preview(request: BatchFixRequest, issues: list[DataIssue], start_time: float) -> BatchFixResponse:
    picked = [(issue, _first_fix(issue, request.auto_apply_safe)) for issue in issues]
    results = [
        BatchFixResult(issue_id=issue.issue_id, fix_id=fix.fix_id, success=True, affected_rows=fix.estimated_rows_affected)
        for issue, fix in picked
        if fix
    ]
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


def _batch_results(applied_fixes: list[AppliedFix], errors: list[str]) -> list[BatchFixResult]:
    done = [
        BatchFixResult(issue_id=a.issue_id, fix_id=a.fix_id, success=a.success,
                       affected_rows=a.rows_affected, error=a.error_message)
        for a in applied_fixes
    ]
    # An error string names no issue, so its entry cannot either.
    return done + [BatchFixResult(issue_id="", fix_id="", success=False, error=error) for error in errors]


async def _batch_applied(
    request: BatchFixRequest, user_id: str, user_data: UserData, record: DataIssueRecord,
    issues: list[DataIssue], start_time: float,
) -> BatchFixResponse:
    df = await get_dataframe_from_s3(_download_url(user_data))
    transformed_df, applied_fixes, errors = await FixSuggestionEngine().apply_batch_fixes(
        df=df,
        issues=issues,
        user_id=user_id,
        auto_apply_safe_only=request.auto_apply_safe,
        stop_on_error=request.stop_on_error,
    )
    new_version_id = None
    if applied_fixes:
        new_version_id = await _record_batch(user_data, user_id, record, (df, transformed_df), issues, applied_fixes)
    results = _batch_results(applied_fixes, errors)
    return BatchFixResponse(
        success=len(errors) == 0,
        dataset_id=request.dataset_id,
        total_fixes=len(results),
        successful_fixes=len(applied_fixes),
        failed_fixes=len(errors),
        results=results,
        total_rows_affected=sum(a.rows_affected for a in applied_fixes),
        execution_time_ms=int((time.time() - start_time) * 1000),
        new_version_id=new_version_id,
        warnings=errors,
    )


async def _record_batch(
    user_data: UserData, user_id: str, record: DataIssueRecord, frames: tuple[pd.DataFrame, pd.DataFrame],
    issues: list[DataIssue], applied_fixes: list[AppliedFix],
) -> str:
    """One history step for every fix that was applied; the new file's URL."""
    fixed_ids = {a.issue_id for a in applied_fixes}
    new_file_path = await _record_fixes(
        user_data, user_id, frames, [i for i in issues if i.issue_id in fixed_ids], applied_fixes
    )
    for applied in applied_fixes:
        record.add_applied_fix(applied)
        record.mark_issue_fixed(applied.issue_id)
    await record.save()
    return new_file_path


@router.post("/batch-fix", response_model=BatchFixResponse)
@discards_uploads_on_reported_failure
@holds_the_dataset(
    lambda kw: None if kw["request"].preview_mode else kw["request"].dataset_id,
    lambda kw: BatchFixResponse(success=False, dataset_id=kw["request"].dataset_id, error=DATASET_BUSY),
)
async def batch_apply_fixes(
    request: BatchFixRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Apply multiple fixes in batch, as one step of the dataset's transformation history.

    Can optionally apply only safe fixes automatically.
    """
    start_time = time.time()
    try:
        user_data = await _owned_upload(request.dataset_id, current_user_id)
        record = await _latest_record(request.dataset_id, current_user_id)
        issues = _issues_to_fix(record, request.issue_ids)
        if request.preview_mode:
            return _batch_preview(request, issues, start_time)
        return await _batch_applied(request, current_user_id, user_data, record, issues, start_time)
    except HTTPException:
        raise
    except (ValidationError, OperationError, NotFoundError) as e:  # a domain error says what it is (#269)
        return BatchFixResponse(success=False, dataset_id=request.dataset_id, error=e.message)
    except Exception:
        logger.exception("Batch fix failed")
        return BatchFixResponse(
            success=False,
            dataset_id=request.dataset_id,
            execution_time_ms=int((time.time() - start_time) * 1000),
            error=internal_error_message("Batch fix"),
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
        ).sort("-detected_at").skip(skip).limit(per_page).to_list()

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
        raise HTTPException(status_code=500, detail="Internal server error") from e
