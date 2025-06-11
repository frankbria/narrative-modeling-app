"""
Tests for schema inference service
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date

from app.services.data_processing.schema_inference import SchemaInferenceService, DataType


@pytest.fixture
def schema_service():
    """Create schema inference service instance"""
    return SchemaInferenceService(sample_size=100)


@pytest.fixture
def sample_dataframe():
    """Create sample dataframe with various data types"""
    # Create date strings instead of datetime objects to test detection
    date_strings = pd.date_range(start='2020-01-01', periods=100, freq='D').strftime('%Y-%m-%d %H:%M:%S').tolist()
    
    return pd.DataFrame({
        'id': range(1, 101),
        'name': [f'Person {i}' for i in range(1, 101)],
        'age': np.random.randint(18, 80, 100),
        'salary': np.random.uniform(30000, 150000, 100),
        'email': [f'user{i}@example.com' for i in range(1, 101)],
        'phone': ['555-' + str(1000 + i) + '-' + str(np.random.randint(1000, 9999)) for i in range(100)],
        'joined_date': date_strings,
        'is_active': np.random.choice([True, False], 100),
        'department': np.random.choice(['Sales', 'Engineering', 'Marketing', 'HR'], 100),
        'website': [f'https://example{i}.com' for i in range(1, 101)],
        'discount': [f'{np.random.randint(5, 50)}%' for i in range(100)],
        'price': ['$' + str(round(np.random.uniform(10, 1000), 2)) for i in range(100)]
    })


class TestSchemaInference:
    """Test schema inference functionality"""

    async def test_integer_detection(self, schema_service):
        """Test integer type detection"""
        df = pd.DataFrame({'col': [1, 2, 3, 4, 5]})
        schema = await schema_service.infer_schema(df)
        
        assert len(schema.columns) == 1
        assert schema.columns[0].data_type == DataType.INTEGER
        assert schema.columns[0].nullable is False

    async def test_float_detection(self, schema_service):
        """Test float type detection"""
        df = pd.DataFrame({'col': [1.5, 2.7, 3.14, 4.0, 5.9]})
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.FLOAT

    async def test_boolean_detection(self, schema_service):
        """Test boolean type detection"""
        df = pd.DataFrame({'col': [True, False, True, True, False]})
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.BOOLEAN

    async def test_email_detection(self, schema_service):
        """Test email pattern detection"""
        df = pd.DataFrame({
            'col': ['test@example.com', 'user@domain.org', 'admin@test.co.uk']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.EMAIL

    async def test_phone_detection(self, schema_service):
        """Test phone number pattern detection"""
        df = pd.DataFrame({
            'col': ['555-123-4567', '(555) 987-6543', '+1 555 234 5678']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.PHONE

    async def test_url_detection(self, schema_service):
        """Test URL pattern detection"""
        df = pd.DataFrame({
            'col': ['https://example.com', 'http://test.org', 'https://sub.domain.com/path']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.URL

    async def test_currency_detection(self, schema_service):
        """Test currency pattern detection"""
        df = pd.DataFrame({
            'col': ['$100.50', '$1,234.56', '$999', '€50.00', '£75.25']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.CURRENCY

    async def test_percentage_detection(self, schema_service):
        """Test percentage pattern detection"""
        df = pd.DataFrame({
            'col': ['10%', '25.5%', '100%', '0%', '99.9%']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.PERCENTAGE

    async def test_date_detection(self, schema_service):
        """Test date type detection"""
        df = pd.DataFrame({
            'col': ['2023-01-01', '2023-12-31', '2023-06-15']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.DATE

    async def test_datetime_detection(self, schema_service):
        """Test datetime type detection"""
        df = pd.DataFrame({
            'col': ['2023-01-01 10:30:00', '2023-12-31 23:59:59', '2023-06-15 12:00:00']
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.DATETIME

    async def test_categorical_detection(self, schema_service):
        """Test categorical type detection"""
        df = pd.DataFrame({
            'col': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B'] * 10
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.CATEGORICAL
        assert schema.columns[0].cardinality == 3

    async def test_text_detection(self, schema_service):
        """Test text type detection"""
        df = pd.DataFrame({
            'col': [
                'This is a long text that contains many words and should be detected as text type',
                'Another long sentence with multiple words that exceeds typical string length',
                'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor'
            ]
        })
        schema = await schema_service.infer_schema(df)
        
        assert schema.columns[0].data_type == DataType.TEXT

    async def test_mixed_types_dataframe(self, schema_service, sample_dataframe):
        """Test schema inference on dataframe with mixed types"""
        schema = await schema_service.infer_schema(sample_dataframe)
        
        # Check that all columns are detected
        assert schema.column_count == len(sample_dataframe.columns)
        assert schema.row_count == len(sample_dataframe)
        
        # Check specific column types
        column_types = {col.name: col.data_type for col in schema.columns}
        
        assert column_types['id'] == DataType.INTEGER
        assert column_types['name'] == DataType.STRING
        assert column_types['age'] == DataType.INTEGER
        assert column_types['salary'] == DataType.FLOAT
        assert column_types['email'] == DataType.EMAIL
        assert column_types['phone'] == DataType.PHONE
        assert column_types['joined_date'] == DataType.DATETIME
        assert column_types['is_active'] == DataType.BOOLEAN
        assert column_types['department'] == DataType.CATEGORICAL
        assert column_types['website'] == DataType.URL
        assert column_types['discount'] == DataType.PERCENTAGE
        assert column_types['price'] == DataType.CURRENCY

    async def test_nullable_detection(self, schema_service):
        """Test nullable field detection"""
        df = pd.DataFrame({
            'col_with_nulls': [1, 2, None, 4, 5],
            'col_without_nulls': [1, 2, 3, 4, 5]
        })
        schema = await schema_service.infer_schema(df)
        
        columns = {col.name: col for col in schema.columns}
        assert columns['col_with_nulls'].nullable is True
        assert columns['col_with_nulls'].null_count == 1
        assert columns['col_with_nulls'].null_percentage == 20.0
        
        assert columns['col_without_nulls'].nullable is False
        assert columns['col_without_nulls'].null_count == 0

    async def test_unique_detection(self, schema_service):
        """Test unique value detection"""
        df = pd.DataFrame({
            'unique_col': [1, 2, 3, 4, 5],
            'duplicate_col': [1, 1, 2, 2, 3]
        })
        schema = await schema_service.infer_schema(df)
        
        columns = {col.name: col for col in schema.columns}
        assert columns['unique_col'].unique is True
        assert columns['unique_col'].cardinality == 5
        
        assert columns['duplicate_col'].unique is False
        assert columns['duplicate_col'].cardinality == 3

    async def test_min_max_values(self, schema_service):
        """Test min/max value calculation"""
        df = pd.DataFrame({
            'numeric': [1, 5, 3, 2, 4],
            'dates': pd.to_datetime(['2023-01-01', '2023-12-31', '2023-06-15', '2023-03-15', '2023-09-01'])
        })
        schema = await schema_service.infer_schema(df)
        
        columns = {col.name: col for col in schema.columns}
        
        # Numeric min/max
        assert columns['numeric'].min_value == 1.0
        assert columns['numeric'].max_value == 5.0
        assert columns['numeric'].mean_value == 3.0
        
        # Date min/max
        assert '2023-01-01' in columns['dates'].min_value
        assert '2023-12-31' in columns['dates'].max_value

    async def test_sample_values(self, schema_service):
        """Test sample value collection"""
        df = pd.DataFrame({
            'col': ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        })
        schema = await schema_service.infer_schema(df)
        
        assert len(schema.columns[0].sample_values) == 5  # Default top 5
        assert all(val in ['A', 'B', 'C', 'D', 'E', 'F', 'G'] 
                  for val in schema.columns[0].sample_values)

    async def test_confidence_score(self, schema_service):
        """Test inference confidence calculation"""
        # High confidence - consistent types
        df_high = pd.DataFrame({
            'col': [1, 2, 3, 4, 5]
        })
        schema_high = await schema_service.infer_schema(df_high)
        assert schema_high.inference_confidence > 0.8
        
        # Lower confidence - mixed types that might be ambiguous
        df_low = pd.DataFrame({
            'col': ['1', '2', 'three', '4', '5']
        })
        schema_low = await schema_service.infer_schema(df_low)
        # Should detect as string, but confidence might be lower due to numeric-like values
        assert schema_low.columns[0].data_type == DataType.STRING