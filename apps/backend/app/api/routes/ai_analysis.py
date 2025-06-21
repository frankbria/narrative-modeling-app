"""
API routes for AI-powered data analysis using MCP
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.services.mcp_integration import mcp_service, MCPAnalysisRequest, MCPAnalysisResponse
from app.services.s3_service import s3_service
from app.services.dataset_summarization import dataset_summarization_service, DatasetSummaryRequest


router = APIRouter()


class AnalysisRequest(BaseModel):
    """Request model for AI analysis"""
    file_id: str = Field(..., description="ID of the file to analyze")
    analysis_type: str = Field(default="comprehensive", pattern="^(comprehensive|statistical|quality|summary)$")
    include_visualization: bool = Field(default=True, description="Include AI-generated visualizations")
    custom_prompts: Optional[list[str]] = Field(default=None, description="Custom analysis prompts")


@router.post("/analyze/{file_id}", response_model=MCPAnalysisResponse)
async def analyze_with_ai(
    file_id: str = Path(..., description="File ID"),
    request: AnalysisRequest = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Perform AI-powered analysis on processed data using MCP tools
    """
    # Use path parameter if request body not provided
    if request is None:
        request = AnalysisRequest(file_id=file_id)
    
    try:
        # Get file metadata from database
        user_data = await UserData.find_one(
            UserData.id == file_id,
            UserData.user_id == current_user_id
        )
        
        if not user_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        if not user_data.is_processed:
            raise HTTPException(
                status_code=400, 
                detail="File must be processed before AI analysis. Please process the file first."
            )
        
        # Prepare data for MCP analysis
        sample_data = user_data.data_preview[:50] if user_data.data_preview else []
        
        # Perform AI analysis
        analysis_result = await mcp_service.analyze_dataset(
            file_id=str(user_data.id),
            schema=user_data.schema,
            statistics=user_data.statistics,
            quality_report=user_data.quality_report,
            sample_data=sample_data,
            analysis_type=request.analysis_type
        )
        
        # Store analysis results (optional - could cache in DB)
        # For now, just return the results
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.get("/insights/{file_id}")
async def get_cached_insights(
    file_id: str = Path(..., description="File ID"),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get cached AI insights for a file (if available)
    """
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    # For now, return a message about caching
    # In production, would retrieve from cache/database
    return {
        "file_id": str(user_data.id),
        "message": "Cached insights not implemented yet. Use /analyze endpoint for fresh analysis.",
        "cached": False
    }


@router.post("/chat/{file_id}")
async def chat_with_data(
    file_id: str = Path(..., description="File ID"),
    query: str = "",
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Interactive chat with data using AI
    """
    user_data = await UserData.find_one(
        UserData.id == file_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not user_data.is_processed:
        raise HTTPException(status_code=400, detail="File must be processed first")
    
    # TODO: Implement chat functionality with MCP
    # For now, return a placeholder response
    
    return {
        "file_id": str(user_data.id),
        "query": query,
        "response": "Chat functionality with MCP will be implemented soon.",
        "suggestions": [
            "What are the main patterns in this data?",
            "Show me outliers in the dataset",
            "What columns have missing values?",
            "Generate a summary of key insights"
        ]
    }


@router.post("/summarize/{file_id}")
async def generate_ai_summary(
    file_id: str = Path(..., description="File ID"),
    focus_areas: Optional[list[str]] = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Generate an AI-powered summary of the dataset
    """
    try:
        # Get file metadata from database
        user_data = await UserData.find_one(
            UserData.id == file_id,
            UserData.user_id == current_user_id
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        if not user_data.is_processed:
            raise HTTPException(
                status_code=400, 
                detail="File must be processed before generating summary"
            )

        # Create summary request
        summary_request = DatasetSummaryRequest(
            file_id=str(user_data.id),
            schema=user_data.schema,
            statistics=user_data.statistics,
            quality_report=user_data.quality_report,
            sample_data=user_data.data_preview[:20] if user_data.data_preview else None,
            focus_areas=focus_areas or ["patterns", "quality", "relationships", "recommendations"]
        )

        # Generate summary
        summary = await dataset_summarization_service.generate_comprehensive_summary(summary_request)

        # Optionally save to database
        user_data.aiSummary = summary
        await user_data.save()
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


@router.get("/health")
async def check_mcp_health():
    """
    Check if MCP server is available and healthy
    """
    is_healthy = await mcp_service.check_health()
    
    return {
        "mcp_available": is_healthy,
        "status": "healthy" if is_healthy else "unavailable",
        "message": "MCP server is operational" if is_healthy else "MCP server is not responding"
    }