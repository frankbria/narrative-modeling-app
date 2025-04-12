from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.services.visualization_cache import (
    generate_and_cache_histogram,
    generate_and_cache_boxplot,
    generate_and_cache_correlation_matrix,
)
from app.api.deps import get_current_user_id

router = APIRouter()


@router.get("/histogram/{dataset_id}/{column_name}")
async def get_histogram(
    dataset_id: str,
    column_name: str,
    num_bins: Optional[int] = 50,
    current_user_id: str = Depends(get_current_user_id),
):
    """Get histogram data for a numeric column"""
    try:
        return await generate_and_cache_histogram(dataset_id, column_name, num_bins)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating histogram: {str(e)}"
        )


@router.get("/boxplot/{dataset_id}/{column_name}")
async def get_boxplot(
    dataset_id: str,
    column_name: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """Get boxplot data for a numeric column"""
    try:
        return await generate_and_cache_boxplot(dataset_id, column_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating boxplot: {str(e)}"
        )


@router.get("/correlation/{dataset_id}")
async def get_correlation_matrix(
    dataset_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """Get correlation matrix for numeric columns"""
    try:
        return await generate_and_cache_correlation_matrix(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating correlation matrix: {str(e)}"
        )
