from datetime import datetime
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd
from app.models.visualization_cache import (
    VisualizationCache,
    HistogramData,
    BoxplotData,
    CorrelationMatrixData,
)
from app.models.user_data import UserData
from app.utils.s3 import get_file_from_s3
from app.utils.plotting import (
    generate_histogram,
    generate_boxplot,
    generate_correlation_matrix,
)


async def get_cached_visualization(
    dataset_id: str, visualization_type: str, column_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Get cached visualization data if it exists"""
    cache = await VisualizationCache.find_one(
        VisualizationCache.dataset_id == dataset_id,
        VisualizationCache.visualization_type == visualization_type,
        VisualizationCache.column_name == column_name,
    )
    return cache.data if cache else None


async def cache_visualization(
    dataset_id: str,
    visualization_type: str,
    data: Dict[str, Any],
    column_name: Optional[str] = None,
) -> VisualizationCache:
    """Cache visualization data"""
    cache = await VisualizationCache.find_one(
        VisualizationCache.dataset_id == dataset_id,
        VisualizationCache.visualization_type == visualization_type,
        VisualizationCache.column_name == column_name,
    )

    if cache:
        cache.data = data
        cache.updated_at = datetime.utcnow()
        await cache.save()
    else:
        cache = VisualizationCache(
            dataset_id=dataset_id,
            visualization_type=visualization_type,
            column_name=column_name,
            data=data,
        )
        await cache.save()

    return cache


async def generate_and_cache_histogram(
    dataset_id: str, column_name: str, num_bins: int = 50
) -> Dict[str, Any]:
    """Generate and cache histogram data for a numeric column"""
    # Get cached data if it exists
    cached_data = await get_cached_visualization(dataset_id, "histogram", column_name)
    if cached_data:
        return cached_data

    # Get dataset from S3
    dataset = await UserData.get(dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")

    df = pd.read_csv(get_file_from_s3(dataset.s3_url))

    # Calculate histogram
    counts, bin_edges = np.histogram(df[column_name].dropna(), bins=num_bins)
    bins = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]

    histogram_data = HistogramData(
        bins=bins, counts=counts.tolist(), bin_edges=bin_edges.tolist()
    )

    # Cache the data
    await cache_visualization(
        dataset_id, "histogram", histogram_data.dict(), column_name
    )

    return histogram_data.dict()


async def generate_and_cache_boxplot(
    dataset_id: str, column_name: str
) -> Dict[str, Any]:
    """Generate and cache boxplot data for a numeric column"""
    # Get cached data if it exists
    cached_data = await get_cached_visualization(dataset_id, "boxplot", column_name)
    if cached_data:
        return cached_data

    # Get dataset from S3
    dataset = await UserData.get(dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")

    df = pd.read_csv(get_file_from_s3(dataset.s3_url))

    # Calculate boxplot statistics
    q1 = df[column_name].quantile(0.25)
    q3 = df[column_name].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = df[(df[column_name] < lower_bound) | (df[column_name] > upper_bound)][
        column_name
    ].tolist()

    boxplot_data = BoxplotData(
        min=df[column_name].min(),
        q1=q1,
        median=df[column_name].median(),
        q3=q3,
        max=df[column_name].max(),
        outliers=outliers,
    )

    # Cache the data
    await cache_visualization(dataset_id, "boxplot", boxplot_data.dict(), column_name)

    return boxplot_data.dict()


async def generate_and_cache_correlation_matrix(dataset_id: str) -> Dict[str, Any]:
    """Generate and cache correlation matrix for numeric columns"""
    # Get cached data if it exists
    cached_data = await get_cached_visualization(dataset_id, "correlation")
    if cached_data:
        return cached_data

    # Get dataset from S3
    dataset = await UserData.get(dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")

    df = pd.read_csv(get_file_from_s3(dataset.s3_url))

    # Select numeric columns
    numeric_df = df.select_dtypes(include=[np.number])

    # Calculate correlation matrix
    corr_matrix = numeric_df.corr()

    correlation_data = CorrelationMatrixData(
        matrix=corr_matrix.values.tolist(), columns=corr_matrix.columns.tolist()
    )

    # Cache the data
    await cache_visualization(dataset_id, "correlation", correlation_data.dict())

    return correlation_data.dict()
