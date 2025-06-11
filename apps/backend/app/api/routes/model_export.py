"""
Model export API routes
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from app.services.model_export import ModelExportService
from app.api.deps import get_current_user_id


router = APIRouter(prefix="/models", tags=["model-export"])

# Initialize service
export_service = ModelExportService()


# Response Models
class ExportFormat(BaseModel):
    name: str
    extension: str
    description: str
    available: bool


class ExportFormatsResponse(BaseModel):
    formats: List[ExportFormat]


# API Routes
@router.get("/{model_id}/export/formats", response_model=ExportFormatsResponse)
async def get_export_formats(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get available export formats for a model"""
    
    formats = await export_service.get_export_formats()
    
    return ExportFormatsResponse(formats=formats)


@router.get("/{model_id}/export/python")
async def export_python_code(
    model_id: str,
    include_preprocessing: bool = Query(default=True, description="Include preprocessing pipeline"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Export model as Python inference code"""
    
    try:
        code, filename = await export_service.export_python_code(
            model_id=model_id,
            user_id=current_user_id,
            include_preprocessing=include_preprocessing
        )
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(code.encode('utf-8')),
            media_type="text/x-python",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{model_id}/export/onnx")
async def export_onnx(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export model to ONNX format"""
    
    try:
        onnx_bytes, filename = await export_service.export_model_onnx(
            model_id=model_id,
            user_id=current_user_id
        )
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(onnx_bytes),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ONNX export failed: {str(e)}")


@router.get("/{model_id}/export/pmml")
async def export_pmml(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export model to PMML format"""
    
    try:
        pmml_content, filename = await export_service.export_model_pmml(
            model_id=model_id,
            user_id=current_user_id
        )
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(pmml_content.encode('utf-8')),
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PMML export failed: {str(e)}")


@router.get("/{model_id}/export/docker")
async def export_docker_container(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export model as Docker container package"""
    
    try:
        zip_bytes, filename = await export_service.export_docker_container(
            model_id=model_id,
            user_id=current_user_id
        )
        
        # Return as downloadable ZIP file
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker export failed: {str(e)}")


@router.post("/{model_id}/export/{format_type}")
async def export_model_custom(
    model_id: str,
    format_type: str,
    options: Dict[str, Any] = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export model with custom options"""
    
    if options is None:
        options = {}
    
    try:
        if format_type == "python":
            code, filename = await export_service.export_python_code(
                model_id=model_id,
                user_id=current_user_id,
                include_preprocessing=options.get("include_preprocessing", True)
            )
            
            return StreamingResponse(
                io.BytesIO(code.encode('utf-8')),
                media_type="text/x-python",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        elif format_type == "onnx":
            onnx_bytes, filename = await export_service.export_model_onnx(
                model_id=model_id,
                user_id=current_user_id
            )
            
            return StreamingResponse(
                io.BytesIO(onnx_bytes),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        elif format_type == "pmml":
            pmml_content, filename = await export_service.export_model_pmml(
                model_id=model_id,
                user_id=current_user_id
            )
            
            return StreamingResponse(
                io.BytesIO(pmml_content.encode('utf-8')),
                media_type="application/xml",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        elif format_type == "docker":
            zip_bytes, filename = await export_service.export_docker_container(
                model_id=model_id,
                user_id=current_user_id
            )
            
            return StreamingResponse(
                io.BytesIO(zip_bytes),
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {format_type}")
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{model_id}/export")
async def get_model_export_info(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get export information and options for a model"""
    
    from app.models.ml_model import MLModel
    
    # Get model details
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": current_user_id
    })
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get available formats
    formats = await export_service.get_export_formats()
    
    return {
        "model_id": model.model_id,
        "model_name": model.name,
        "model_version": model.version,
        "algorithm": model.algorithm,
        "problem_type": model.problem_type,
        "feature_count": model.n_features,
        "available_formats": formats,
        "export_endpoints": {
            "python": f"/api/v1/models/{model_id}/export/python",
            "onnx": f"/api/v1/models/{model_id}/export/onnx",
            "pmml": f"/api/v1/models/{model_id}/export/pmml",
            "docker": f"/api/v1/models/{model_id}/export/docker"
        },
        "usage_examples": {
            "curl_python": f"curl -H 'Authorization: Bearer $TOKEN' '{request.url.scheme}://{request.url.netloc}/api/v1/models/{model_id}/export/python' -o model_inference.py",
            "curl_docker": f"curl -H 'Authorization: Bearer $TOKEN' '{request.url.scheme}://{request.url.netloc}/api/v1/models/{model_id}/export/docker' -o model_container.zip"
        }
    }