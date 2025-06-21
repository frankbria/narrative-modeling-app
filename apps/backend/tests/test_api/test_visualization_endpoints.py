"""
Tests for visualization API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd
import numpy as np
import io
from datetime import datetime

from app.main import app
from app.models.user_data import UserData
from beanie import PydanticObjectId


@pytest.fixture
def mock_user_data():
    """Mock user data object"""
    return UserData(
        id=PydanticObjectId(),
        user_id="test-user-123",
        filename="test_data.csv",
        original_filename="test-file-123.csv",
        s3_url="s3://test-bucket/test-file.csv",
        num_rows=100,
        num_columns=5,
        data_schema=[],
        is_processed=True
    )


@pytest.fixture
def sample_dataframe():
    """Sample dataframe for visualization testing"""
    np.random.seed(42)
    return pd.DataFrame({
        'id': range(1, 101),
        'value': np.random.normal(50, 10, 100),
        'category': np.random.choice(['A', 'B', 'C'], 100),
        'price': np.random.uniform(10, 100, 100),
        'quantity': np.random.randint(1, 20, 100),
        'date': pd.date_range('2024-01-01', periods=100, freq='D')
    })


class TestVisualizationAPI:
    """Test suite for visualization endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_histogram_success(self, authorized_client, mock_user_data, sample_dataframe):
        """Test getting histogram data"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.services.visualization_cache.generate_and_cache_histogram', new_callable=AsyncMock) as mock_histogram:
                mock_histogram.return_value = {
                    "bins": [20, 30, 40, 50, 60, 70, 80],
                    "counts": [5, 15, 30, 25, 15, 10],
                    "binEdges": [20, 30, 40, 50, 60, 70, 80, 90],
                    "min": 20.5,
                    "max": 89.3
                }
                
                response = authorized_client.get(f"/api/v1/visualizations/histogram/{mock_user_data.id}/value?bins=10")
                
                assert response.status_code == 200
                data = response.json()
                assert "bins" in data
                assert "counts" in data
                assert len(data["bins"]) == len(data["counts"])
                assert data["min"] < data["max"]
    
    @pytest.mark.asyncio
    async def test_get_boxplot_success(self, authorized_client, mock_user_data):
        """Test getting boxplot data"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.services.visualization_cache.generate_and_cache_boxplot', new_callable=AsyncMock) as mock_boxplot:
                mock_boxplot.return_value = {
                    "min": 15.2,
                    "q1": 42.5,
                    "median": 50.0,
                    "q3": 57.5,
                    "max": 84.8,
                    "outliers": [5.1, 95.3, 98.7]
                }
                
                response = authorized_client.get(f"/api/v1/visualizations/boxplot/{mock_user_data.id}/value")
                
                assert response.status_code == 200
                data = response.json()
                assert data["min"] <= data["q1"] <= data["median"] <= data["q3"] <= data["max"]
                assert "outliers" in data
                assert len(data["outliers"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_correlation_matrix_success(self, authorized_client, mock_user_data):
        """Test getting correlation matrix"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.services.visualization_cache.generate_and_cache_correlation_matrix', new_callable=AsyncMock) as mock_corr:
                mock_corr.return_value = {
                    "columns": ["value", "price", "quantity"],
                    "matrix": [
                        [1.0, 0.85, -0.2],
                        [0.85, 1.0, -0.15],
                        [-0.2, -0.15, 1.0]
                    ]
                }
                
                response = authorized_client.get(f"/api/v1/visualizations/correlation/{mock_user_data.id}")
                
                assert response.status_code == 200
                data = response.json()
                assert "columns" in data
                assert "matrix" in data
                assert len(data["columns"]) == len(data["matrix"])
                assert all(len(row) == len(data["columns"]) for row in data["matrix"])
    
    @pytest.mark.asyncio
    async def test_get_scatter_plot_success(self, authorized_client, mock_user_data, sample_dataframe):
        """Test getting scatter plot data"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.utils.s3.get_file_from_s3') as mock_s3:
                csv_buffer = io.BytesIO()

                sample_dataframe.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                mock_s3.return_value = csv_buffer
                
                response = authorized_client.get(f"/api/v1/visualizations/scatter/{mock_user_data.id}/price/quantity")
                
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert len(data["data"]) == 100
                assert "xLabel" in data and data["xLabel"] == "price"
                assert "yLabel" in data and data["yLabel"] == "quantity"
                assert "correlation" in data
    
    @pytest.mark.asyncio
    async def test_get_scatter_plot_with_filters(self, authorized_client, mock_user_data, sample_dataframe):
        """Test scatter plot with filters"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.utils.s3.get_file_from_s3') as mock_s3:
                csv_buffer = io.BytesIO()

                sample_dataframe.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                mock_s3.return_value = csv_buffer
                
                filters = '[{"column": "category", "operator": "equals", "value": "A"}]'
                response = authorized_client.get(
                    f"/api/v1/visualizations/scatter/{mock_user_data.id}/price/quantity?filters={filters}"
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert len(data["data"]) < 100  # Filtered data should have fewer points
    
    @pytest.mark.asyncio
    async def test_get_line_chart_success(self, authorized_client, mock_user_data, sample_dataframe):
        """Test getting line chart data"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.utils.s3.get_file_from_s3') as mock_s3:
                csv_buffer = io.BytesIO()

                sample_dataframe.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                mock_s3.return_value = csv_buffer
                
                response = authorized_client.get(
                    f"/api/v1/visualizations/line/{mock_user_data.id}/date?y_columns=value,price"
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert "lines" in data
                assert len(data["lines"]) == 2
                assert data["lines"][0]["dataKey"] == "value"
                assert data["lines"][1]["dataKey"] == "price"
    
    @pytest.mark.asyncio
    async def test_get_time_series_success(self, authorized_client, mock_user_data, sample_dataframe):
        """Test getting time series data"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.utils.s3.get_file_from_s3') as mock_s3:
                csv_buffer = io.BytesIO()

                sample_dataframe.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                mock_s3.return_value = csv_buffer
                
                response = authorized_client.get(
                    f"/api/v1/visualizations/timeseries/{mock_user_data.id}/date/value"
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "timestamps" in data
                assert "values" in data
                assert "label" in data
                assert len(data["timestamps"]) == len(data["values"])
                assert data["label"] == "value"
    
    @pytest.mark.asyncio
    async def test_visualization_with_invalid_column(self, authorized_client, mock_user_data, sample_dataframe):
        """Test visualization with non-existent column"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            with patch('app.utils.s3.get_file_from_s3') as mock_s3:
                csv_buffer = io.BytesIO()

                sample_dataframe.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)
                mock_s3.return_value = csv_buffer
                
                response = authorized_client.get(
                    f"/api/v1/visualizations/scatter/{mock_user_data.id}/nonexistent/value"
                )
                
                assert response.status_code == 500
                assert "Error generating scatter plot" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_visualization_unauthorized(self, async_test_client, mock_user_data):
        """Test visualization without authorization"""
        # Use async_test_client without auth override to test unauthorized access
        response = await async_test_client.get(f"/api/v1/visualizations/histogram/{mock_user_data.id}/value")
        assert response.status_code == 401