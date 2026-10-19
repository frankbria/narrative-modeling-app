"""
API routes for AI-powered data analysis using MCP
"""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.billing import enforcement
from app.billing.enforcement import quota
from app.middleware.error_handlers import internal_error_message
from app.models.user_data import UserData
from app.services.ai_chat import ChatRequest, ai_chat_service
from app.services.dataset_summarization import (
    DatasetSummaryRequest,
    EnhancedAISummary,
    dataset_summarization_service,
)
from app.services.mcp_integration import MCPAnalysisResponse, mcp_service
from app.utils.circuit_breaker import CircuitBreakerOpen

logger = logging.getLogger(__name__)

router = APIRouter()


def _as_object_id(file_id: str):
    """Coerce a path string to the ObjectId `UserData.id` actually stores.

    `UserData.id` is a `PydanticObjectId`, so comparing it to the raw string from
    the path matches nothing and the caller gets a 404 for a document that exists
    (#409). A malformed id is passed through unchanged so the query simply misses
    and the route still answers 404 rather than raising InvalidId as a 500.

    Mirrors `model_training.py`, which carries the same coercion.
    """
    try:
        return PydanticObjectId(file_id)
    except (InvalidId, ValueError, TypeError):
        return file_id



class AnalysisRequest(BaseModel):
    """Request model for AI analysis"""
    file_id: str = Field(..., description="ID of the file to analyze")
    analysis_type: str = Field(default="comprehensive", pattern="^(comprehensive|statistical|quality|summary)$")
    include_visualization: bool = Field(default=True, description="Include AI-generated visualizations")
    custom_prompts: list[str] | None = Field(default=None, description="Custom analysis prompts")


async def _processed_upload(file_id: str, user_id: str, unprocessed: str) -> UserData:
    """The caller's dataset, once it has been processed.

    404 when it is not theirs or does not exist (the two answer alike); 400 with
    ``unprocessed`` when processing has not run, since both routes read its results.
    """
    user_data = await UserData.find_one(
        UserData.id == _as_object_id(file_id),
        UserData.user_id == user_id
    )
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    if not user_data.is_processed:
        raise HTTPException(status_code=400, detail=unprocessed)
    return user_data


async def _analysis(user_data: UserData, user_id: str, analysis_type: str) -> MCPAnalysisResponse:
    """Ask the analysis service about the dataset.

    The MCP tool reads the dataset server-side from (dataset_id, user_id) and
    authorizes ownership itself (#506); the stored schema, statistics and sample
    enrich the summary and the fallback only.
    """
    return await mcp_service.analyze_dataset(
        dataset_id=str(user_data.id),
        user_id=user_id,  # the authenticated caller, not what the row says
        schema=user_data.schema or {},
        statistics=user_data.statistics or {},
        quality_report=user_data.quality_report or {},
        sample_data=(user_data.data_preview or [])[:50],
        analysis_type=analysis_type,
    )


@router.post("/analyze/{file_id}", response_model=MCPAnalysisResponse, dependencies=[Depends(quota("ai_calls"))])
async def analyze_with_ai(
    http_request: Request,
    file_id: str = Path(..., description="File ID"),
    request: AnalysisRequest | None = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Perform AI-powered analysis on processed data using MCP tools
    """
    # Use path parameter if request body not provided
    request = request or AnalysisRequest(file_id=file_id)

    try:
        user_data = await _processed_upload(
            file_id, current_user_id,
            "File must be processed before AI analysis. Please process the file first.",
        )

        analysis_result = await _analysis(user_data, current_user_id, request.analysis_type)
        if analysis_result.metadata.get("fallback_mode"):
            # The analysis service did not answer, so this is the rule-based summary
            # computed here: nothing was bought, the reserved unit goes back (#461).
            await enforcement.release(http_request)

        return analysis_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.get("/insights/{file_id}", dependencies=[Depends(quota("ai_calls"))])
async def get_cached_insights(
    file_id: str = Path(..., description="File ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get cached AI insights for a file.

    Not implemented (#274): there is no insight cache. Rather than return a
    misleading 200, this signals 501 so callers fall back to the working
    ``POST /analyze`` / ``POST /summarize`` endpoints for fresh analysis.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Cached insights are not available. "
               "Use POST /api/v1/ai/analyze/{file_id} for fresh analysis.",
    )


@router.post("/chat", dependencies=[Depends(quota("ai_calls"))])
async def chat(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    """
    Dataset chat (#461). The Next.js `/api/chat` proxy forwards here so the call is
    reserved against `ai_calls` and refunded by the middleware on any failure.
    """
    try:
        reply = await ai_chat_service.reply(request)
    except CircuitBreakerOpen:
        # Open breaker or the #768 daily ceiling: chat has no rule-based answer to
        # fall back to, so it is a 503, which the refund middleware hands back.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI chat is temporarily unavailable. Please try again later.",
        ) from None
    if reply is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI chat is not configured on this deployment.",
        )
    return {"reply": reply}


@router.post("/chat/{file_id}", dependencies=[Depends(quota("ai_calls"))])
async def chat_with_data(
    file_id: str = Path(..., description="File ID"),
    query: str = "",
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Interactive chat with data using AI.

    Not implemented (#274): the MCP-backed chat does not exist yet. Rather than
    return a fake "coming soon" 200 with canned suggestions, this signals 501.
    Use ``POST /analyze`` / ``POST /summarize`` for real AI analysis today.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Interactive chat is not available yet. "
               "Use POST /api/v1/ai/summarize/{file_id} for an AI summary.",
    )


def _summary_request(user_data: UserData, focus_areas: list[str] | None) -> DatasetSummaryRequest:
    """What the summarizer is told about the dataset: its parts as stored, null
    included. The summarizer reads a null part as an empty one (#981)."""
    return DatasetSummaryRequest(
        file_id=str(user_data.id),
        schema=user_data.schema,
        statistics=user_data.statistics,
        quality_report=user_data.quality_report,
        sample_data=user_data.data_preview[:20] if user_data.data_preview else None,
        focus_areas=focus_areas or ["patterns", "quality", "relationships", "recommendations"],
    )


async def _settle(user_data: UserData, summary: EnhancedAISummary, http_request: Request) -> None:
    """Charge for the summary only if a model wrote it, and keep it only if it is one.

    A rule-based or failed summary is not a model call (no key, breaker open, or the
    #768 daily ceiling), so the reserved unit goes back. A failed one is returned to
    the caller but never stored: it used to replace the dataset's real summary (#981).
    The write sets the one field, so it cannot revert what changed while the summary
    was being made.
    """
    if summary.model_used in ("fallback", "error"):
        await enforcement.release(http_request)
    if summary.model_used != "error":
        await user_data.set({UserData.aiSummary: summary})


@router.post("/summarize/{file_id}", dependencies=[Depends(quota("ai_calls"))])
async def generate_ai_summary(
    http_request: Request,
    file_id: str = Path(..., description="File ID"),
    focus_areas: list[str] | None = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Generate an AI-powered summary of the dataset
    """
    try:
        user_data = await _processed_upload(
            file_id, current_user_id, "File must be processed before generating summary"
        )

        summary = await dataset_summarization_service.generate_comprehensive_summary(
            _summary_request(user_data, focus_areas)
        )
        await _settle(user_data, summary, http_request)

        return summary
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /ai/summarize failed for %s", file_id)
        raise HTTPException(status_code=500, detail=internal_error_message("The summary"))


@router.get("/health")
async def check_mcp_health(current_user_id: str = Depends(get_current_user_id)):
    """
    Check if MCP server is available and healthy.

    Authenticated like every other handler in this router (#563): the answer is a
    readout of internal deployment state, and each call is an outbound request to
    the MCP server — neither is for anonymous callers. It is not a readiness
    dependency of the app, so it does not live beside the probes in health.py.
    """
    is_healthy = await mcp_service.check_health()
    
    return {
        "mcp_available": is_healthy,
        "status": "healthy" if is_healthy else "unavailable",
        "message": "MCP server is operational" if is_healthy else "MCP server is not responding"
    }