import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from app.models.user_data import UserData
from app.models.visualization_cache import (
    BoxplotData,
    CorrelationMatrixData,
    HistogramData,
    VisualizationCache,
)
from app.services.redis_cache import cache_service
from app.services.s3_service import read_columns_from_bytes, read_dataframe_from_bytes
from app.utils.s3 import get_file_from_s3

logger = logging.getLogger(__name__)

# Only this bin count is cacheable — the cache key does not capture num_bins.
DEFAULT_HISTOGRAM_BINS = 50


def _cache_key(
    dataset_id: str, visualization_type: str, column_name: str | None, source_url: str | None
) -> str:
    """`viz:{dataset}:{type}[:{column}][:{digest of the file}]`. The leading
    `viz:{dataset}:` is what erasure and a move clear by."""
    digest = hashlib.sha1(source_url.encode()).hexdigest()[:12] if source_url else None
    parts = ("viz", dataset_id, visualization_type, column_name, digest)
    return ":".join(part for part in parts if part)


async def _from_redis(cache_key: str) -> dict[str, Any] | None:
    """Best effort: a cache that cannot be read degrades to MongoDB."""
    try:
        return await cache_service.get(cache_key)
    except Exception as e:
        logger.warning(f"Redis cache read failed for {cache_key}: {e}")
        return None


async def _to_redis(cache_key: str, data: dict[str, Any]) -> None:
    try:
        await cache_service.set(cache_key, data, ttl=3600)  # 1 hour
    except Exception as e:
        logger.warning(f"Redis cache write failed for {cache_key}: {e}")


async def _stored(
    dataset_id: str, visualization_type: str, column_name: str | None
) -> tuple[UserData, VisualizationCache | None]:
    """The dataset, and its stored entry for this chart if there is one."""
    dataset = await UserData.get(dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")
    # Link fields are stored as DBRefs — query by the referenced document id
    query_filter = {"dataset_id.$id": dataset.id, "visualization_type": visualization_type}
    if column_name:
        query_filter["column_name"] = column_name
    return dataset, await VisualizationCache.find_one(query_filter)


def _chart_of(entry: VisualizationCache | None, source_url: str | None) -> dict[str, Any] | None:
    """A stored entry's data, if it is a chart of the file asked about (#964).

    A request that began before a dataset moved can finish after it and store a chart
    of the old file; the entry says which file it is of, and is served only for that
    one. A caller that names no file gets whatever is stored, as before.
    """
    if not entry or not entry.data:
        return None
    if source_url is not None and entry.source_url != source_url:
        return None
    return entry.data


async def get_cached_visualization(
    dataset_id: str,
    visualization_type: str,
    column_name: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any] | None:
    """Get cached visualization data from Redis first, then MongoDB.

    `source_url` is the file the caller would compute the chart from; only an entry
    computed from that file is returned."""
    cache_key = _cache_key(dataset_id, visualization_type, column_name, source_url)
    cached_data = await _from_redis(cache_key)
    if cached_data:
        return cached_data

    _, entry = await _stored(dataset_id, visualization_type, column_name)
    chart = _chart_of(entry, source_url)
    if chart is not None:
        await _to_redis(cache_key, chart)  # for faster access next time
    return chart


async def cache_visualization(
    dataset_id: str,
    visualization_type: str,
    data: dict[str, Any],
    column_name: str | None = None,
    source_url: str | None = None,
) -> VisualizationCache:
    """Cache visualization data in both Redis and MongoDB, as a chart of `source_url`."""
    await _to_redis(_cache_key(dataset_id, visualization_type, column_name, source_url), data)

    dataset, cache = await _stored(dataset_id, visualization_type, column_name)
    if cache:
        cache.data = data
        cache.source_url = source_url
        cache.updated_at = datetime.now(UTC)
    else:
        # Create a new cache entry (Beanie converts the document into a Link)
        cache = VisualizationCache(
            dataset_id=dataset,
            visualization_type=visualization_type,
            column_name=column_name,
            data=data,
            source_url=source_url,
        )
    await cache.save()
    return cache


async def _dataset_frame(s3_url: str, columns: list[str] | None = None) -> pd.DataFrame:
    """The dataset at ``s3_url`` as a frame, read by what its bytes are (#733).

    These readers used ``pd.read_csv`` on every object. A transformation rewrites the
    dataset as Parquet, so every chart failed for a dataset transformed once, and a
    workbook or JSON upload failed from the start. Blocking download and parse, so off
    the event loop (#514).
    """
    # A chart of one column reads that column (#712); the correlation matrix, which
    # is of every numeric column, reads the file whole.
    def read() -> pd.DataFrame:
        content = get_file_from_s3(s3_url).getvalue()
        if columns is None:
            return read_dataframe_from_bytes(content)
        return read_columns_from_bytes(content, columns)

    return await asyncio.to_thread(read)


async def _dataset(dataset_id: str) -> UserData:
    dataset = await UserData.get(dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")
    return dataset


async def _cached_default_histogram(
    dataset_id: str, column_name: str, use_cache: bool, source_url: str | None = None
) -> dict[str, Any] | None:
    """The cached histogram, when the request is for the default bin count and the
    cached entry has it."""
    if not use_cache:
        return None
    cached_data = await get_cached_visualization(dataset_id, "histogram", column_name, source_url)
    # Guard against entries written by the old bin-agnostic path (or any
    # non-default shape that predates this fix): only serve a cache hit whose
    # bin count actually matches the default. Otherwise the caller recomputes,
    # overwriting the stale entry.
    if cached_data and len(cached_data.get("counts", [])) == DEFAULT_HISTOGRAM_BINS:
        return cached_data
    return None


async def generate_and_cache_histogram(
    dataset_id: str, column_name: str, num_bins: int = DEFAULT_HISTOGRAM_BINS
) -> dict[str, Any]:
    """Generate and cache histogram data for a numeric column"""
    # The visualization cache is keyed by (dataset, type, column) only — it does
    # not capture num_bins — so only the default bin count may be served from /
    # written to the cache. Non-default counts are always computed fresh,
    # otherwise a later request would reuse an earlier bin shape (e.g. 50 bins
    # returned after the user selects 20). See issue #170.
    use_cache = num_bins == DEFAULT_HISTOGRAM_BINS
    # The dataset first: a cached chart is served only if it is of the file the
    # dataset is at now (#964).
    dataset = await _dataset(dataset_id)
    cached_data = await _cached_default_histogram(dataset_id, column_name, use_cache, dataset.s3_url)
    if cached_data:
        return cached_data

    # Offload the blocking download + parse off the event loop (#514).
    df = await _dataset_frame(dataset.s3_url, [column_name])

    # Calculate histogram
    counts, bin_edges = np.histogram(df[column_name].dropna(), bins=num_bins)
    bins = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]

    histogram_data = HistogramData(
        bins=bins, counts=counts.tolist(), bin_edges=bin_edges.tolist()
    )

    if use_cache:
        await cache_visualization(
            dataset_id, "histogram", histogram_data.model_dump(), column_name, dataset.s3_url
        )

    return histogram_data.model_dump()


async def generate_and_cache_boxplot(
    dataset_id: str, column_name: str
) -> dict[str, Any]:
    """Generate and cache boxplot data for a numeric column"""
    dataset = await _dataset(dataset_id)
    cached_data = await get_cached_visualization(dataset_id, "boxplot", column_name, dataset.s3_url)
    if cached_data:
        return cached_data

    # Offload the blocking download + parse off the event loop (#514).
    df = await _dataset_frame(dataset.s3_url, [column_name])

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
    await cache_visualization(
        dataset_id, "boxplot", boxplot_data.model_dump(), column_name, dataset.s3_url
    )

    return boxplot_data.model_dump()


async def generate_and_cache_correlation_matrix(dataset_id: str) -> dict[str, Any]:
    """Generate and cache correlation matrix for numeric columns"""
    dataset = await _dataset(dataset_id)
    cached_data = await get_cached_visualization(dataset_id, "correlation", source_url=dataset.s3_url)
    if cached_data:
        return cached_data

    # Offload the blocking download + parse off the event loop (#514).
    df = await _dataset_frame(dataset.s3_url)

    # Select numeric columns
    numeric_df = df.select_dtypes(include=[np.number])

    # Calculate correlation matrix
    corr_matrix = numeric_df.corr()

    # Convert numpy array to list and get column names
    matrix_values = corr_matrix.values.tolist()
    columns = list(corr_matrix.columns)  # Convert Index to list

    correlation_data = CorrelationMatrixData(matrix=matrix_values, columns=columns)

    # Cache the data
    await cache_visualization(
        dataset_id, "correlation", correlation_data.model_dump(), source_url=dataset.s3_url
    )

    return correlation_data.model_dump()
