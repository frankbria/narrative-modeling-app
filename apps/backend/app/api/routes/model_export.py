"""
Model export API routes
"""
import io
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.nextauth_auth import get_current_user_id
from app.services.exceptions import NotFoundError
from app.services.model_export import ExportFormatUnavailable, ModelExportService
from app.utils.filenames import attachment_disposition

router = APIRouter(prefix="/models", tags=["model-export"])

# Initialize service
export_service = ModelExportService()


_MEDIA_TYPES = {
    "python": "text/x-python",
    "onnx": "application/octet-stream",
    "pmml": "application/xml",
    "docker": "application/zip",
}


def _download(content: bytes | str, media_type: str, filename: str) -> StreamingResponse:
    """The export as a file download. The filename carries the model's name, which
    its owner chose, so the header is built by the one builder that cannot be
    broken out of (#648)."""
    body = content.encode("utf-8") if isinstance(content, str) else content
    return StreamingResponse(
        io.BytesIO(body),
        media_type=media_type,
        headers={"Content-Disposition": attachment_disposition(filename)},
    )


async def _export(
    format_type: str, model_id: str, user_id: str, options: dict[str, Any] | None
) -> tuple[bytes | str, str]:
    """The export in the named format, and the filename the service gives it."""
    if format_type == "python":
        return await export_service.export_python_code(
            model_id=model_id,
            user_id=user_id,
            include_preprocessing=(options or {}).get("include_preprocessing", True),
        )
    exporters: dict[str, Callable[..., Awaitable[tuple[bytes | str, str]]]] = {
        "onnx": export_service.export_model_onnx,
        "pmml": export_service.export_model_pmml,
        "docker": export_service.export_docker_container,
    }
    if format_type not in exporters:
        raise ValueError(f"Unsupported export format: {format_type}")
    return await exporters[format_type](model_id=model_id, user_id=user_id)


# Response Models
class ExportFormat(BaseModel):
    name: str
    extension: str
    description: str
    available: bool


class ExportFormatsResponse(BaseModel):
    formats: list[ExportFormat]


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
        
        return _download(code, "text/x-python", filename)
        
    except NotFoundError as e:  # missing or another tenant's model — identical answers
        raise HTTPException(status_code=404, detail=e.message)
    except ExportFormatUnavailable as e:  # converter not installed here
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:  # conversion failed
        raise HTTPException(status_code=400, detail=str(e))
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
        
        return _download(onnx_bytes, "application/octet-stream", filename)
        
    except NotFoundError as e:  # missing or another tenant's model — identical answers
        raise HTTPException(status_code=404, detail=e.message)
    except ExportFormatUnavailable as e:  # converter not installed here
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:  # conversion failed
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
        
        return _download(pmml_content, "application/xml", filename)
        
    except NotFoundError as e:  # missing or another tenant's model — identical answers
        raise HTTPException(status_code=404, detail=e.message)
    except ExportFormatUnavailable as e:  # converter not installed here
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:  # conversion failed
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
        
        return _download(zip_bytes, "application/zip", filename)
        
    except NotFoundError as e:  # missing or another tenant's model — identical answers
        raise HTTPException(status_code=404, detail=e.message)
    except ExportFormatUnavailable as e:  # converter not installed here
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:  # conversion failed
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker export failed: {str(e)}")


@router.post("/{model_id}/export/{format_type}")
async def export_model_custom(
    model_id: str,
    format_type: str,
    options: dict[str, Any] | None = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """Export model with custom options"""

    try:
        content, filename = await _export(format_type, model_id, current_user_id, options)
        return _download(content, _MEDIA_TYPES[format_type], filename)

    except NotFoundError as e:  # missing or another tenant's model — identical answers
        raise HTTPException(status_code=404, detail=e.message)
    except ExportFormatUnavailable as e:  # converter not installed here
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:  # conversion failed, or a format that is not one of ours
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{model_id}/export")
async def get_model_export_info(
    model_id: str,
    request: Request,
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