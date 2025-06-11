"""
Tests for the main data processor service
"""

import pytest
import pandas as pd
import numpy as np
from io import BytesIO

from app.services.data_processing.data_processor import DataProcessor, ProcessedData


@pytest.fixture
def data_processor():
    """Create data processor instance"""
    return DataProcessor()


@pytest.fixture
def csv_data():
    """Create sample CSV data"""
    df = pd.DataFrame({
        'id': range(1, 101),
        'name': [f'Person {i}' for i in range(1, 101)],
        'email': [f'user{i}@example.com' for i in range(1, 101)],
        'age': np.random.randint(18, 65, 100),
        'salary': np.random.uniform(30000, 150000, 100),
        'department': np.random.choice(['Sales', 'Engineering', 'Marketing', 'HR'], 100),
        'joined_date': pd.date_range(start='2020-01-01', periods=100, freq='D').strftime('%Y-%m-%d'),
        'is_active': np.random.choice([True, False], 100)
    })
    
    # Convert to CSV bytes
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()


@pytest.fixture
def json_data():
    """Create sample JSON data"""
    data = [
        {
            'id': i,
            'product': f'Product {i}',
            'price': round(np.random.uniform(10, 1000), 2),
            'in_stock': bool(np.random.choice([0, 1])),
            'category': np.random.choice(['Electronics', 'Clothing', 'Food', 'Books'])
        }
        for i in range(1, 51)
    ]
    
    import json
    return json.dumps(data).encode('utf-8')


@pytest.fixture
def excel_data():
    """Create sample Excel data"""
    df = pd.DataFrame({
        'order_id': range(1, 26),
        'customer': [f'Customer {i}' for i in range(1, 26)],
        'amount': np.random.uniform(10, 500, 25),
        'date': pd.date_range(start='2023-01-01', periods=25, freq='D')
    })
    
    # Convert to Excel bytes
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False, engine='openpyxl')
    return excel_buffer.getvalue()


class TestDataProcessor:
    """Test data processor functionality"""

    async def test_process_csv_file(self, data_processor, csv_data):
        """Test processing CSV file"""
        result = await data_processor.process_bytes(
            file_bytes=csv_data,
            filename='test_data.csv',
            file_type='csv'
        )
        
        assert isinstance(result, ProcessedData)
        assert len(result.dataframe) == 100
        assert len(result.dataframe.columns) == 8
        assert result.file_metadata['file_type'] == 'csv'
        
        # Check schema
        assert result.schema is not None
        assert result.schema.column_count == 8
        assert result.schema.row_count == 100
        
        # Check statistics
        assert result.statistics is not None
        assert len(result.statistics.column_statistics) == 8
        
        # Check quality report
        assert result.quality_report is not None
        assert result.quality_report.overall_quality_score > 0
        
        # Check dataframe
        assert result.dataframe is not None
        assert len(result.dataframe) == 100

    async def test_process_json_file(self, data_processor, json_data):
        """Test processing JSON file"""
        result = await data_processor.process_bytes(
            file_bytes=json_data,
            filename='test_data.json',
            file_type='json'
        )
        
        assert len(result.dataframe) == 50
        assert len(result.dataframe.columns) == 5
        assert result.file_metadata['file_type'] == 'json'
        
        # Check that all processing components ran
        assert result.schema is not None
        assert result.statistics is not None
        assert result.quality_report is not None

    async def test_process_excel_file(self, data_processor, excel_data):
        """Test processing Excel file"""
        result = await data_processor.process_bytes(
            file_bytes=excel_data,
            filename='test_data.xlsx',
            file_type='excel'
        )
        
        assert len(result.dataframe) == 25
        assert len(result.dataframe.columns) == 4
        assert result.file_metadata['file_type'] == 'excel'

    async def test_schema_inference_integration(self, data_processor, csv_data):
        """Test that schema inference correctly identifies data types"""
        result = await data_processor.process_bytes(
            file_bytes=csv_data,
            filename='test_data.csv',
            file_type='csv'
        )
        
        # Check specific column types
        column_types = {col.name: col.data_type for col in result.schema.columns}
        
        assert column_types['id'] == 'integer'
        assert column_types['name'] == 'string'
        assert column_types['email'] == 'email'
        assert column_types['age'] == 'integer'
        assert column_types['salary'] == 'float'
        assert column_types['department'] == 'categorical'
        assert column_types['joined_date'] == 'date'
        assert column_types['is_active'] == 'boolean'

    async def test_statistics_integration(self, data_processor, csv_data):
        """Test that statistics are correctly calculated"""
        result = await data_processor.process_bytes(
            file_bytes=csv_data,
            filename='test_data.csv',
            file_type='csv'
        )
        
        # Find age statistics
        age_stats = next(s for s in result.statistics.column_statistics if s.column_name == 'age')
        
        assert age_stats.mean is not None
        assert age_stats.min_value >= 18
        assert age_stats.max_value <= 65
        assert age_stats.null_count == 0
        
        # Find salary statistics
        salary_stats = next(s for s in result.statistics.column_statistics if s.column_name == 'salary')
        
        assert salary_stats.mean is not None
        assert salary_stats.min_value >= 30000
        assert salary_stats.max_value <= 150000

    async def test_quality_assessment_integration(self, data_processor, csv_data):
        """Test that quality assessment runs correctly"""
        result = await data_processor.process_bytes(
            file_bytes=csv_data,
            filename='test_data.csv',
            file_type='csv'
        )
        
        # Should have high quality score for clean data
        assert result.quality_report.overall_quality_score > 0.8
        
        # Check dimension scores
        assert result.quality_report.dimension_scores is not None
        assert len(result.quality_report.dimension_scores) == 6

    async def test_get_preview(self, data_processor, csv_data):
        """Test data preview functionality"""
        result = await data_processor.process_bytes(
            file_bytes=csv_data,
            filename='test_data.csv',
            file_type='csv'
        )
        
        # Test default preview
        preview = result.get_preview()
        assert 'columns' in preview
        assert 'data' in preview
        assert 'total_rows' in preview
        assert len(preview['data']) <= 100
        
        # Test limited preview
        limited_preview = result.get_preview(rows=10)
        assert len(limited_preview['data']) == 10

    async def test_get_summary(self, data_processor, csv_data):
        """Test summary generation"""
        result = await data_processor.process_bytes(
            file_bytes=csv_data,
            filename='test_data.csv',
            file_type='csv'
        )
        
        summary = result.get_summary()
        
        assert 'filename' in summary
        assert 'file_type' in summary
        assert 'row_count' in summary
        assert 'column_count' in summary
        assert 'overall_quality_score' in summary
        assert 'column_types' in summary
        assert 'processing_time_seconds' in summary

    async def test_invalid_file_handling(self, data_processor):
        """Test handling of invalid file data"""
        # Pandas is quite forgiving, so this test just verifies processing completes
        invalid_data = b"This is not valid CSV data\nIt's just random text"
        
        result = await data_processor.process_bytes(
            file_bytes=invalid_data,
            filename='invalid.csv',
            file_type='csv'
        )
        
        # Should still process, but with minimal structure
        assert result is not None
        assert len(result.dataframe.columns) > 0

    async def test_empty_file_handling(self, data_processor):
        """Test handling of empty file"""
        empty_csv = b""
        
        with pytest.raises(Exception):
            await data_processor.process_bytes(
                file_bytes=empty_csv,
                filename='empty.csv',
                file_type='csv'
            )

    async def test_file_with_mixed_types(self, data_processor):
        """Test file with mixed data types in columns"""
        # Create CSV with mixed types
        mixed_df = pd.DataFrame({
            'mixed_col': [1, '2', 3.0, 'four', 5],
            'dates': ['2023-01-01', '2023-01-02', 'not a date', '2023-01-04', '2023-01-05']
        })
        
        csv_buffer = BytesIO()
        mixed_df.to_csv(csv_buffer, index=False)
        mixed_csv = csv_buffer.getvalue()
        
        result = await data_processor.process_bytes(
            file_bytes=mixed_csv,
            filename='mixed.csv',
            file_type='csv'
        )
        
        # Should still process successfully
        assert len(result.dataframe) == 5
        assert len(result.dataframe.columns) == 2
        
        # Schema should identify as string due to mixed types
        column_types = {col.name: col.data_type for col in result.schema.columns}
        assert column_types['mixed_col'] == 'string'

    async def test_large_file_simulation(self, data_processor):
        """Test processing of larger file"""
        # Create larger dataset
        large_df = pd.DataFrame({
            'id': range(10000),
            'value': np.random.randn(10000),
            'category': np.random.choice(['A', 'B', 'C', 'D'], 10000),
            'timestamp': pd.date_range(start='2020-01-01', periods=10000, freq='h')
        })
        
        csv_buffer = BytesIO()
        large_df.to_csv(csv_buffer, index=False)
        large_csv = csv_buffer.getvalue()
        
        result = await data_processor.process_bytes(
            file_bytes=large_csv,
            filename='large.csv',
            file_type='csv'
        )
        
        assert len(result.dataframe) == 10000
        assert len(result.dataframe.columns) == 4
        
        # Should have processed_at timestamp
        assert result.processed_at is not None

    async def test_special_characters_handling(self, data_processor):
        """Test handling of special characters in data"""
        special_df = pd.DataFrame({
            'text': ['Hello, World!', 'Test & Demo', 'Price: $100', 'Email@test.com', '50% off'],
            'numbers': [1.23, 4.56, 7.89, 10.11, 12.13]
        })
        
        csv_buffer = BytesIO()
        special_df.to_csv(csv_buffer, index=False)
        special_csv = csv_buffer.getvalue()
        
        result = await data_processor.process_bytes(
            file_bytes=special_csv,
            filename='special.csv',
            file_type='csv'
        )
        
        assert len(result.dataframe) == 5
        assert len(result.dataframe.columns) == 2
        
        # Should handle special characters correctly
        assert result.dataframe is not None
        assert len(result.dataframe) == 5