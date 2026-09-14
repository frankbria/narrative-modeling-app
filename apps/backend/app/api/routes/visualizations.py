import asyncio
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.services.redis_cache import cache_service
from app.services.visualization_cache import (
    generate_and_cache_boxplot,
    generate_and_cache_correlation_matrix,
    generate_and_cache_histogram,
)
from app.utils.s3 import get_file_from_s3

router = APIRouter()

# A chart can't draw (and a browser can't hold) a million points; cap what we return so
# the payload and its serialization stay bounded (#513). The point count a line/scatter
# actually renders is a few thousand.
MAX_CHART_POINTS = 5000
# TTL for cached chart payloads (#514): repeated views of the same chart must not
# re-download and re-parse the whole dataset.
_CHART_CACHE_TTL = 300


async def _load_dataframe(s3_url: str) -> pd.DataFrame:
    """Download + parse the dataset OFF the event loop (#514).

    The handlers are ``async`` but this is blocking I/O + a full pandas parse; running it
    inline stalled the worker for every other request for the whole download+parse.
    """
    return await asyncio.to_thread(lambda: pd.read_csv(get_file_from_s3(s3_url)))


def _apply_filters(df: pd.DataFrame, filters: str | None) -> pd.DataFrame:
    """Apply the optional JSON filter list (raises json.JSONDecodeError on bad JSON,
    which the handlers map to 400)."""
    if not filters:
        return df
    for f in json.loads(filters):
        col, op, val = f["column"], f["operator"], f["value"]
        if op == "equals":
            df = df[df[col] == val]
        elif op == "greater_than":
            df = df[df[col] > val]
        elif op == "less_than":
            df = df[df[col] < val]
        elif op == "contains":
            df = df[df[col].str.contains(str(val), na=False)]
        elif op == "between" and isinstance(val, list):
            df = df[(df[col] >= val[0]) & (df[col] <= val[1])]
    return df


def _downsample(df: pd.DataFrame, *, ordered: bool) -> tuple[pd.DataFrame, bool, float]:
    """Cap the frame at MAX_CHART_POINTS (#513). ``ordered`` (line/timeseries) takes an
    evenly-spaced stride to preserve the curve's shape; otherwise a deterministic random
    sample. Returns (frame, sampled, sample_rate)."""
    n = len(df)
    if n <= MAX_CHART_POINTS:
        return df, False, 1.0
    if ordered:
        idx = np.linspace(0, n - 1, MAX_CHART_POINTS, dtype=int)
        return df.iloc[idx], True, MAX_CHART_POINTS / n
    return df.sample(n=MAX_CHART_POINTS, random_state=0), True, MAX_CHART_POINTS / n


def _chart_cache_key(kind: str, dataset_id: str, *parts: Any) -> str:
    raw = "|".join([kind, dataset_id, *[str(p) for p in parts]])
    return f"viz:{kind}:{dataset_id}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


@router.get("/histogram/{dataset_id}/{column_name}")
async def get_histogram(
    dataset_id: str,
    column_name: str,
    num_bins: int | None = 50,
    current_user_id: str = Depends(get_current_user_id),
):
    """Get histogram data for a numeric column"""
    try:
        # Verify dataset ownership before generating visualization
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        return await generate_and_cache_histogram(
            dataset_id, column_name, num_bins if num_bins is not None else 50
        )
    except HTTPException:
        raise
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
        # Verify dataset ownership before generating visualization
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        return await generate_and_cache_boxplot(dataset_id, column_name)
    except HTTPException:
        raise
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
        # Verify dataset ownership before generating visualization
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        return await generate_and_cache_correlation_matrix(dataset_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating correlation matrix: {str(e)}"
        )


@router.get("/scatter/{dataset_id}/{x_column}/{y_column}")
async def get_scatter_plot(
    dataset_id: str,
    x_column: str,
    y_column: str,
    filters: str | None = Query(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get scatter plot data for two columns"""
    try:
        # Get dataset
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        cache_key = _chart_cache_key("scatter", dataset_id, x_column, y_column, filters)
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return cached

        df = await _load_dataframe(dataset.s3_url)
        df = _apply_filters(df, filters)

        # Correlation is computed over the FULL (filtered) data, before downsampling.
        correlation = df[x_column].corr(df[y_column])

        # Cap the returned points (#513) and build them vectorized (no iterrows, #513).
        sample, sampled, sample_rate = _downsample(df, ordered=False)
        xs = pd.to_numeric(sample[x_column], errors="coerce")
        ys = pd.to_numeric(sample[y_column], errors="coerce")
        data_points = [
            {"x": None if pd.isna(x) else float(x), "y": None if pd.isna(y) else float(y)}
            for x, y in zip(xs.to_numpy(), ys.to_numpy(), strict=True)
        ]

        payload = {
            "data": data_points,
            "xLabel": x_column,
            "yLabel": y_column,
            "correlation": float(correlation) if not np.isnan(correlation) else None,
            "sampled": sampled,
            "sample_rate": sample_rate,
            "total_rows": int(len(df)),
        }
        await cache_service.set(cache_key, payload, ttl=_CHART_CACHE_TTL)
        return payload

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid filter format")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating scatter plot: {str(e)}"
        )


@router.get("/line/{dataset_id}/{x_column}")
async def get_line_chart(
    dataset_id: str,
    x_column: str,
    y_columns: str = Query(...),
    filters: str | None = Query(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get line chart data"""
    try:
        # Get dataset
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        cache_key = _chart_cache_key("line", dataset_id, x_column, y_columns, filters)
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return cached

        df = await _load_dataframe(dataset.s3_url)
        df = _apply_filters(df, filters)

        # Parse y_columns
        y_cols = [c for c in y_columns.split(",") if c in df.columns]

        # Cap the returned points, preserving the line's shape (#513), then build
        # vectorized from records (no iterrows).
        sample, sampled, sample_rate = _downsample(df, ordered=True)

        def _native_x(value):
            if pd.isna(value):
                return None
            if isinstance(value, np.integer):
                return int(value)
            if isinstance(value, np.floating):
                return float(value)
            return str(value)

        records = sample[[x_column, *y_cols]].to_dict("records")
        data = []
        for rec in records:
            point = {"x": _native_x(rec[x_column])}
            for y_col in y_cols:
                v = rec[y_col]
                point[y_col] = None if pd.isna(v) else float(v)
            data.append(point)

        lines = [{"dataKey": col, "label": col} for col in y_cols]

        payload = {
            "data": data,
            "lines": lines,
            "xLabel": x_column,
            "yLabel": "Value",
            "sampled": sampled,
            "sample_rate": sample_rate,
            "total_rows": int(len(df)),
        }
        await cache_service.set(cache_key, payload, ttl=_CHART_CACHE_TTL)
        return payload

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid filter format")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating line chart: {str(e)}"
        )


@router.get("/timeseries/{dataset_id}/{time_column}/{value_column}")
async def get_time_series(
    dataset_id: str,
    time_column: str,
    value_column: str,
    filters: str | None = Query(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get time series data"""
    try:
        # Get dataset
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        cache_key = _chart_cache_key("timeseries", dataset_id, time_column, value_column, filters)
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return cached

        df = await _load_dataframe(dataset.s3_url)
        df = _apply_filters(df, filters)

        # Convert time column to datetime and sort
        df[time_column] = pd.to_datetime(df[time_column])
        df = df.sort_values(time_column)

        # Cap the returned points with an evenly-spaced stride to preserve the curve (#513).
        sample, sampled, sample_rate = _downsample(df, ordered=True)

        timestamps = sample[time_column].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
        values = sample[value_column].fillna(0).tolist()

        payload = {
            "timestamps": timestamps,
            "values": values,
            "label": value_column,
            "sampled": sampled,
            "sample_rate": sample_rate,
            "total_rows": int(len(df)),
        }
        await cache_service.set(cache_key, payload, ttl=_CHART_CACHE_TTL)
        return payload

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid filter format")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating time series: {str(e)}"
        )
