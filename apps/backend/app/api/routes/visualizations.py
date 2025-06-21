from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.services.visualization_cache import (
    generate_and_cache_histogram,
    generate_and_cache_boxplot,
    generate_and_cache_correlation_matrix,
)
from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.utils.s3 import get_file_from_s3
import pandas as pd
import json
import numpy as np
from datetime import datetime

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


@router.get("/scatter/{dataset_id}/{x_column}/{y_column}")
async def get_scatter_plot(
    dataset_id: str,
    x_column: str,
    y_column: str,
    filters: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get scatter plot data for two columns"""
    try:
        # Get dataset
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load data
        df = pd.read_csv(get_file_from_s3(dataset.file_path))
        
        # Apply filters if provided
        if filters:
            filter_list = json.loads(filters)
            for f in filter_list:
                col = f['column']
                op = f['operator']
                val = f['value']
                
                if op == 'equals':
                    df = df[df[col] == val]
                elif op == 'greater_than':
                    df = df[df[col] > val]
                elif op == 'less_than':
                    df = df[df[col] < val]
                elif op == 'contains':
                    df = df[df[col].str.contains(str(val), na=False)]
                elif op == 'between' and isinstance(val, list):
                    df = df[(df[col] >= val[0]) & (df[col] <= val[1])]
        
        # Prepare scatter data
        data_points = []
        for _, row in df.iterrows():
            data_points.append({
                'x': float(row[x_column]) if pd.notna(row[x_column]) else None,
                'y': float(row[y_column]) if pd.notna(row[y_column]) else None
            })
        
        # Calculate correlation
        correlation = df[x_column].corr(df[y_column])
        
        return {
            'data': data_points,
            'xLabel': x_column,
            'yLabel': y_column,
            'correlation': float(correlation) if not np.isnan(correlation) else None
        }
        
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
    filters: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get line chart data"""
    try:
        # Get dataset
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load data
        df = pd.read_csv(get_file_from_s3(dataset.file_path))
        
        # Apply filters if provided
        if filters:
            filter_list = json.loads(filters)
            for f in filter_list:
                col = f['column']
                op = f['operator']
                val = f['value']
                
                if op == 'equals':
                    df = df[df[col] == val]
                elif op == 'greater_than':
                    df = df[df[col] > val]
                elif op == 'less_than':
                    df = df[df[col] < val]
                elif op == 'contains':
                    df = df[df[col].str.contains(str(val), na=False)]
                elif op == 'between' and isinstance(val, list):
                    df = df[(df[col] >= val[0]) & (df[col] <= val[1])]
        
        # Parse y_columns
        y_cols = y_columns.split(',')
        
        # Prepare line chart data
        data = []
        for _, row in df.iterrows():
            point = {'x': row[x_column]}
            for y_col in y_cols:
                if y_col in df.columns:
                    point[y_col] = float(row[y_col]) if pd.notna(row[y_col]) else None
            data.append(point)
        
        # Prepare lines info
        lines = [{'dataKey': col, 'label': col} for col in y_cols]
        
        return {
            'data': data,
            'lines': lines,
            'xLabel': x_column,
            'yLabel': 'Value'
        }
        
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
    filters: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get time series data"""
    try:
        # Get dataset
        dataset = await UserData.get(dataset_id)
        if not dataset or dataset.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load data
        df = pd.read_csv(get_file_from_s3(dataset.file_path))
        
        # Apply filters if provided
        if filters:
            filter_list = json.loads(filters)
            for f in filter_list:
                col = f['column']
                op = f['operator']
                val = f['value']
                
                if op == 'equals':
                    df = df[df[col] == val]
                elif op == 'greater_than':
                    df = df[df[col] > val]
                elif op == 'less_than':
                    df = df[df[col] < val]
                elif op == 'contains':
                    df = df[df[col].str.contains(str(val), na=False)]
                elif op == 'between' and isinstance(val, list):
                    df = df[(df[col] >= val[0]) & (df[col] <= val[1])]
        
        # Convert time column to datetime
        df[time_column] = pd.to_datetime(df[time_column])
        
        # Sort by time
        df = df.sort_values(time_column)
        
        # Prepare time series data
        timestamps = df[time_column].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
        values = df[value_column].fillna(0).tolist()
        
        return {
            'timestamps': timestamps,
            'values': values,
            'label': value_column
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid filter format")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating time series: {str(e)}"
        )
