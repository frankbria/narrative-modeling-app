import asyncio
import hashlib
import json
import numbers
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.services.redis_cache import cache_service
from app.services.s3_service import read_columns_from_bytes
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


async def _load_dataframe(s3_url: str, columns: set[str]) -> pd.DataFrame:
    """Download the dataset and parse the columns a chart needs, OFF the event loop (#514).

    The handlers are ``async`` but this is blocking I/O + a pandas parse; running it
    inline stalled the worker for every other request for the whole download+parse.
    Read by what the bytes are, not as CSV (#733): the dataset is Parquet once
    transformed, and then only ``columns`` are decoded (#712).
    """
    return await asyncio.to_thread(
        lambda: read_columns_from_bytes(get_file_from_s3(s3_url).getvalue(), columns)
    )


_FILTER_OPERATORS = {"equals", "greater_than", "less_than", "contains", "between"}


def _bad_filter(position: int, problem: str) -> HTTPException:
    return HTTPException(status_code=400, detail=f"Filter {position + 1}: {problem}")


def _parse_filters(filters: str | None, known_columns: list[str] | None) -> list[dict[str, Any]]:
    """The filter list, checked once and before anything is downloaded (#996): a list
    of ``{column, operator, value}`` with a known operator and, when the dataset's
    columns are recorded, a column it has. Anything else is the caller's 400 naming the
    entry, never a 500, and an unknown operator is never skipped silently."""
    if not filters:
        return []
    try:
        parsed = json.loads(filters)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid filter format")
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="Invalid filter format: expected a list of filters")
    for position, entry in enumerate(parsed):
        _check_filter(position, entry, known_columns)
    return parsed


def _check_filter(position: int, entry: Any, known_columns: list[str] | None) -> None:
    if not isinstance(entry, dict) or not {"column", "operator", "value"} <= entry.keys():
        raise _bad_filter(position, "each filter needs a column, an operator and a value")
    if entry["operator"] not in _FILTER_OPERATORS:
        raise _bad_filter(position, f"unknown operator {entry['operator']!r}")
    if entry["operator"] == "between" and not (isinstance(entry["value"], list) and len(entry["value"]) == 2):
        raise _bad_filter(position, "between takes a list of two values")
    if known_columns and entry["column"] not in known_columns:
        raise _bad_filter(position, f"the dataset has no column {entry['column']!r}")


def _columns_needed(chart_columns: list[str], filters: list[dict[str, Any]]) -> set[str]:
    """What a chart reads: the columns it draws and the ones its filters test."""
    return {*chart_columns, *(f["column"] for f in filters)}


def _apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    """Apply the parsed filter list. A column the file lacks, or an operator that does
    not apply to the column's values (``contains`` on numbers, ``greater_than`` text
    against numbers), is the caller's 400."""
    for position, f in enumerate(filters):
        if f["column"] not in df.columns:
            raise _bad_filter(position, f"the dataset has no column {f['column']!r}")
        try:
            df = df[_filter_mask(df[f["column"]], f["operator"], f["value"])]
        except (TypeError, AttributeError, ValueError):
            raise _bad_filter(position, f"{f['operator']} does not apply to the values of {f['column']!r}")
    return df


def _filter_mask(column: pd.Series, operator: str, value: Any) -> pd.Series:
    if operator == "equals":
        return column == value
    if operator == "greater_than":
        return column > value
    if operator == "less_than":
        return column < value
    if operator == "contains":
        return column.str.contains(str(value), na=False)
    return (column >= value[0]) & (column <= value[1])


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


def _chart_cache_key(kind: str, dataset_id: str, s3_url: str | None, *parts: Any) -> str:
    """Cache key that (a) leads with ``dataset_id`` so erasure's ``viz:{dataset_id}:*``
    sweep purges it (#452/#513 — else cached points survive erasure until TTL), and
    (b) folds in ``s3_url`` so a transformation that rewrites the dataset file (which
    changes ``UserData.s3_url`` via ``record_new_file``) invalidates the key instead of
    serving stale data for the TTL window."""
    raw = "|".join([kind, s3_url or "", *[str(p) for p in parts]])
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"viz:{dataset_id}:{kind}:{digest}"


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


async def _chart(
    kind: str,
    dataset_id: str,
    user_id: str,
    columns: list[str],
    filters: str | None,
    build: Callable[[pd.DataFrame], dict[str, Any]],
) -> dict[str, Any]:
    """One chart of the caller's dataset: from the cache, or built from the filtered
    frame of the columns it needs and cached for the next request (#514)."""
    dataset = await UserData.get(dataset_id)
    if not dataset or dataset.user_id != user_id:
        raise HTTPException(status_code=404, detail="Dataset not found")

    cache_key = _chart_cache_key(kind, dataset_id, dataset.s3_url, *columns, filters)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    parsed = _parse_filters(filters, dataset.columns)
    df = await _load_dataframe(dataset.s3_url, _columns_needed(columns, parsed))
    payload = build(_apply_filters(df, parsed))
    await cache_service.set(cache_key, payload, ttl=_CHART_CACHE_TTL)
    return payload


def _scatter_payload(df: pd.DataFrame, x_column: str, y_column: str) -> dict[str, Any]:
    # Correlation is computed over the FULL (filtered) data, before downsampling.
    correlation = df[x_column].corr(df[y_column])

    # Coerce to numeric and DROP rows where either coordinate is missing/non-numeric,
    # rather than emitting {x|y: null} — a scatter point needs both coords, and the
    # frontend ScatterPlotData types x/y as non-nullable numbers and calls .toFixed()
    # on them unguarded. Drop first, then cap the returned points (#513).
    numeric = pd.DataFrame({
        "x": pd.to_numeric(df[x_column], errors="coerce"),
        "y": pd.to_numeric(df[y_column], errors="coerce"),
    }).dropna()
    sample, sampled, sample_rate = _downsample(numeric, ordered=False)
    data_points = [
        {"x": float(x), "y": float(y)}
        for x, y in zip(sample["x"].to_numpy(), sample["y"].to_numpy(), strict=True)
    ]
    return {
        "data": data_points,
        "xLabel": x_column,
        "yLabel": y_column,
        "correlation": float(correlation) if not np.isnan(correlation) else None,
        "sampled": sampled,
        "sample_rate": sample_rate,
        "total_rows": int(len(df)),
    }


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
        return await _chart(
            "scatter", dataset_id, current_user_id, [x_column, y_column], filters,
            lambda df: _scatter_payload(df, x_column, y_column),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating scatter plot: {str(e)}"
        )


def _native_x(value: Any) -> Any:
    """An x value as JSON can carry it: a missing one is null, a number stays a number.

    The records come out of pandas as plain ``int`` and ``float``, which the numpy
    checks this used to make never matched, so a numeric x was sent as text (#712).
    """
    if pd.isna(value):
        return None
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return str(value)
    return int(value) if isinstance(value, numbers.Integral) else float(value)


def _line_point(record: dict[str, Any], x_column: str, y_cols: list[str]) -> dict[str, Any]:
    point = {"x": _native_x(record[x_column])}
    for y_col in y_cols:
        value = record[y_col]
        point[y_col] = None if pd.isna(value) else float(value)
    return point


def _line_payload(df: pd.DataFrame, x_column: str, y_columns: str) -> dict[str, Any]:
    y_cols = [c for c in y_columns.split(",") if c in df.columns]

    # Cap the returned points, preserving the line's shape (#513), then build
    # vectorized from records (no iterrows).
    sample, sampled, sample_rate = _downsample(df, ordered=True)
    records = sample[[x_column, *y_cols]].to_dict("records")
    return {
        "data": [_line_point(record, x_column, y_cols) for record in records],
        "lines": [{"dataKey": col, "label": col} for col in y_cols],
        "xLabel": x_column,
        "yLabel": "Value",
        "sampled": sampled,
        "sample_rate": sample_rate,
        "total_rows": int(len(df)),
    }


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
        return await _chart(
            "line", dataset_id, current_user_id, [x_column, *y_columns.split(",")], filters,
            lambda df: _line_payload(df, x_column, y_columns),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating line chart: {str(e)}"
        )


def _timeseries_payload(df: pd.DataFrame, time_column: str, value_column: str) -> dict[str, Any]:
    # Convert time column to datetime and sort
    df[time_column] = pd.to_datetime(df[time_column])
    df = df.sort_values(time_column)

    # Cap the returned points with an evenly-spaced stride to preserve the curve (#513).
    sample, sampled, sample_rate = _downsample(df, ordered=True)
    return {
        "timestamps": sample[time_column].dt.strftime("%Y-%m-%d %H:%M:%S").tolist(),
        "values": sample[value_column].fillna(0).tolist(),
        "label": value_column,
        "sampled": sampled,
        "sample_rate": sample_rate,
        "total_rows": int(len(df)),
    }


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
        return await _chart(
            "timeseries", dataset_id, current_user_id, [time_column, value_column], filters,
            lambda df: _timeseries_payload(df, time_column, value_column),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating time series: {str(e)}"
        )
