#!/usr/bin/env python3
"""
Final fixes for remaining syntax errors
"""
import re

def fix_visualization_endpoints():
    """Fix test_visualization_endpoints.py"""
    file_path = "tests/test_api/test_visualization_endpoints.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix PydanticObjectId(,
    content = content.replace('PydanticObjectId(,', 'PydanticObjectId(),')
    
    # Fix missing response = authorized_client.get lines
    fixes = [
        # Fix boxplot test
        ('mock_boxplot.return_value = {\n                    "min": 15.2,\n                    "q1": 42.5,\n                    "median": 50.0,\n                    "q3": 57.5,\n                    "max": 84.8,\n                    "outliers": [5.1, 95.3, 98.7]\n                }\n                \n                \n                assert response.status_code == 200',
         'mock_boxplot.return_value = {\n                    "min": 15.2,\n                    "q1": 42.5,\n                    "median": 50.0,\n                    "q3": 57.5,\n                    "max": 84.8,\n                    "outliers": [5.1, 95.3, 98.7]\n                }\n                \n                response = authorized_client.get(f"/api/v1/visualizations/boxplot/{mock_user_data.id}/value")\n                \n                assert response.status_code == 200\n                data = response.json()'),
        
        # Fix correlation test
        ('mock_corr.return_value = {\n                    "columns": ["value", "price", "quantity"],\n                    "matrix": [\n                        [1.0, 0.85, -0.2],\n                        [0.85, 1.0, -0.15],\n                        [-0.2, -0.15, 1.0]\n                    ]\n                }\n                \n                \n                assert response.status_code == 200',
         'mock_corr.return_value = {\n                    "columns": ["value", "price", "quantity"],\n                    "matrix": [\n                        [1.0, 0.85, -0.2],\n                        [0.85, 1.0, -0.15],\n                        [-0.2, -0.15, 1.0]\n                    ]\n                }\n                \n                response = authorized_client.get(f"/api/v1/visualizations/correlation/{mock_user_data.id}")\n                \n                assert response.status_code == 200\n                data = response.json()'),
        
        # Fix scatter plot test
        ('mock_s3.return_value = csv_buffer\n                \n                \n                assert response.status_code == 200',
         'mock_s3.return_value = csv_buffer\n                \n                response = authorized_client.get(f"/api/v1/visualizations/scatter/{mock_user_data.id}/price/quantity")\n                \n                assert response.status_code == 200\n                data = response.json()'),
    ]
    
    for old, new in fixes:
        if old in content:
            content = content.replace(old, new)
    
    # Fix missing csv_buffer initialization in test methods
    # Add csv_buffer = io.BytesIO() before sample_dataframe.to_csv(csv_buffer, index=False)
    content = re.sub(
        r'(\s+)sample_dataframe\.to_csv\(csv_buffer, index=False\)',
        r'\1csv_buffer = io.BytesIO()\n\1sample_dataframe.to_csv(csv_buffer, index=False)',
        content
    )
    
    # Fix missing response = authorized_client.get lines
    content = re.sub(
        r'(\s+)f"/api/v1/visualizations/([^"]+)"\n(\s+)\)',
        r'\1response = authorized_client.get(\n\1    f"/api/v1/visualizations/\2"\n\1)',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_full_workflow():
    """Fix test_full_workflow.py"""
    file_path = "tests/integration/test_full_workflow.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the missing response assignments
    content = re.sub(
        r'response = await async_authorized_client\.post\(\n\n\s+"/api/v1/data/test-file-123/export",',
        r'response = await async_authorized_client.post(\n                        "/api/v1/data/test-file-123/export"',
        content
    )
    
    # Fix UserData instantiations with missing fields
    content = re.sub(
        r'(\s+)mock_user_data = UserData\(\n\s+id="test-file-123",',
        r'\1mock_user_data = UserData(\n\1    id="test-file-123",',
        content
    )
    
    # Fix incomplete UserData instantiations
    content = re.sub(
        r'UserData\(\n\s+s3_url="s3://test-bucket/test-file\.csv",\n\s+data_schema=\[\]\n\s+,',
        r'UserData(\n        id=PydanticObjectId(),\n        user_id="test_user_123",\n        filename="test.csv",\n        original_filename="test.csv",\n        s3_url="s3://test-bucket/test-file.csv",\n        num_rows=100,\n        num_columns=1,\n        data_schema=[],',
        content
    )
    
    # Add missing response assignments for analysis endpoints
    content = re.sub(
        r'(\s+)assert response\.status_code == 200\n(\s+)analysis_data = response\.json\(\)',
        r'\1response = await async_authorized_client.get("/api/v1/ai/analysis/test-file-123")\n\1\n\1assert response.status_code == 200\n\1analysis_data = response.json()',
        content
    )
    
    # Add missing response for histogram
    content = re.sub(
        r'(\s+)assert response\.status_code == 200\n(\s+)\n(\s+)# Test correlation matrix',
        r'\1response = await async_authorized_client.get("/api/v1/visualizations/histogram/test-file-123/age")\n\1\n\1assert response.status_code == 200\n\1\n\1# Test correlation matrix',
        content
    )
    
    # Add missing response for correlation
    content = re.sub(
        r'(\s+)"matrix": \[\[1\.0, 0\.3\], \[0\.3, 1\.0\]\]\n(\s+)\}\n(\s+)\n(\s+)assert response\.status_code == 200',
        r'\1"matrix": [[1.0, 0.3], [0.3, 1.0]]\n\1}\n\1\n\1response = await async_authorized_client.get("/api/v1/visualizations/correlation/test-file-123")\n\1\n\1assert response.status_code == 200',
        content
    )
    
    # Add missing response for analysis
    content = re.sub(
        r'(\s+)assert response\.status_code == 400\n(\s+)assert "must be processed" in response\.json\(\)\["detail"\]',
        r'\1response = await async_authorized_client.get("/api/v1/ai/analysis/unprocessed")\n\1\n\1assert response.status_code == 400\n\1assert "must be processed" in response.json()["detail"]',
        content
    )
    
    # Fix "No newline at end of file" in the middle of the file
    content = content.replace(' No newline at end of file\n', '\n')
    
    # Add missing imports
    if 'from beanie import PydanticObjectId' not in content:
        content = content.replace(
            'from app.models.user_data import UserData',
            'from app.models.user_data import UserData\nfrom beanie import PydanticObjectId'
        )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_data_processing():
    """Fix test_data_processing.py"""
    file_path = "tests/test_api/test_data_processing.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix double response assignments
    content = re.sub(
        r'response = await async_test_client\.post\(\n\s+response = await async_authorized_client\.post\(\n',
        r'response = await async_authorized_client.post(\n',
        content
    )
    
    # Fix missing mock_user_data definitions
    content = re.sub(
        r'with patch\(\'app\.models\.user_data\.UserData\.find_one\', new_callable=AsyncMock\) as mock_find:\n(\s+)mock_find\.return_value = mock_user_data',
        r'mock_user_data = create_mock_user_data(schema=schema_data, is_processed=True)\n        \n        with patch(\'app.models.user_data.UserData.find_one\', new_callable=AsyncMock) as mock_find:\n\1mock_find.return_value = mock_user_data',
        content
    )
    
    # Fix missing response assignments
    content = re.sub(
        r'(\s+)assert response\.status_code == 200\n(\s+)data = response\.json\(\)',
        r'\1response = await async_authorized_client.get("/api/v1/data/test-file-123/schema")\n\1\n\1assert response.status_code == 200\n\1data = response.json()',
        content
    )
    
    # Fix statistics endpoint
    content = re.sub(
        r'(\s+)assert response\.status_code == 200\n(\s+)assert "columns" in data',
        r'\1response = await async_authorized_client.get("/api/v1/data/test-file-123/statistics")\n\1\n\1assert response.status_code == 200\n\1data = response.json()\n\1assert "columns" in data',
        content
    )
    
    # Fix quality report endpoint
    content = re.sub(
        r'(\s+)assert response\.status_code == 200\n(\s+)assert data\["overall_quality_score"\]',
        r'\1response = await async_authorized_client.get("/api/v1/data/test-file-123/quality")\n\1\n\1assert response.status_code == 200\n\1data = response.json()\n\1assert data["overall_quality_score"]',
        content
    )
    
    # Fix missing csv_buffer initialization
    content = re.sub(
        r'(\s+)sample_dataframe\.to_csv\(csv_buffer, index=False\)\n(\s+)mock_s3_download\.return_value = csv_bytes',
        r'\1csv_buffer = io.BytesIO()\n\1sample_dataframe.to_csv(csv_buffer, index=False)\n\1csv_bytes = csv_buffer.getvalue()\n\1mock_s3_download.return_value = csv_bytes',
        content
    )
    
    # Fix missing mock_s3_download reference
    content = content.replace('mock_s3.side_effect = Exception', 'mock_s3_download.side_effect = Exception')
    
    # Fix duplicate response = lines
    content = re.sub(
        r'response = await async_authorized_client\.post\(\n\n\s+"/api/v1/data/process",',
        r'response = await async_authorized_client.post(\n                    "/api/v1/data/process",',
        content
    )
    
    # Remove "No newline at end of file"
    content = content.replace(' No newline at end of file', '')
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_model_training():
    """Fix test_model_training.py"""
    file_path = "tests/test_api/test_model_training.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing response assignments
    content = re.sub(
        r'response = await async_authorized_client\.get\(\n\n\s+"/api/v1/ml/model_123"\n\n\s+\)\n\n\s+data = response\.json\(\)\s+\)',
        r'response = await async_authorized_client.get(\n                    "/api/v1/ml/model_123"\n                )\n                data = response.json()',
        content
    )
    
    # Fix duplicate response/data lines in delete endpoint
    content = re.sub(
        r'response = await async_authorized_client\.get\(\n\n\s+"/api/v1/ml/model_123"\n\n\s+\)\n\n\s+data = response\.json\(\)\s+\)\n\s+assert response\.status_code == 200',
        r'response = await async_authorized_client.delete(\n                    "/api/v1/ml/model_123"\n                )\n                data = response.json()\n            \n            assert response.status_code == 200',
        content
    )
    
    # Fix missing request_data for predict endpoint
    content = re.sub(
        r'(\s+)mock_find\.return_value = AsyncMock\(return_value=MagicMock\(\n(\s+)feature_names=\["feature1", "feature2", "feature3"\]\n(\s+)\)\)\(\)\n(\s+)\n(\s+)"data": \[',
        r'\1mock_find.return_value = AsyncMock(return_value=MagicMock(\n\2feature_names=["feature1", "feature2", "feature3"]\n\3))()\n\4\n\4request_data = {\n\5"data": [',
        content
    )
    
    # Fix missing response for predict
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/predict",\n(\s+)\)\n(\s+)\n(\s+)assert response\.status_code == 200',
        r'\1"/api/v1/ml/model_123/predict",\n\1json=request_data\n\2)\n\3\n\3data = response.json()\n\3\n\4assert response.status_code == 200',
        content
    )
    
    # Fix deactivate endpoint
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/deactivate",\n(\s+)\)\n(\s+)\n(\s+)assert response\.status_code == 200',
        r'\1"/api/v1/ml/model_123/deactivate"\n\2)\n\3\n\3data = response.json()\n\3\n\4assert response.status_code == 200',
        content
    )
    
    # Fix train endpoint missing response
    content = re.sub(
        r'(\s+)"/api/v1/ml/train",\n(\s+)json=request_data,\n(\s+)\)\n(\s+)\n(\s+)assert response\.status_code',
        r'\1"/api/v1/ml/train",\n\2json=request_data\n\3)\n\4\n\5assert response.status_code',
        content
    )
    
    # Fix predict endpoint with missing request_data
    content = re.sub(
        r'(\s+)"data": \[\{"feature1": 1\.0\}\]\n(\s+)\}\n(\s+)\n(\s+)"/api/v1/ml/non_existent/predict",',
        r'\1"data": [{"feature1": 1.0}]\n\2}\n\3\n\3response = await async_authorized_client.post(\n\4"/api/v1/ml/non_existent/predict",\n\4json=request_data',
        content
    )
    
    # Fix missing response assignment
    content = re.sub(
        r'response = await mock_async_client\.',
        r'response = await async_authorized_client.',
        content
    )
    
    # Remove "No newline at end of file"
    content = content.rstrip() + '\n'
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_upload():
    """Fix test_upload.py"""
    file_path = "tests/test_api/test_upload.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing mock_file initializations
    content = re.sub(
        r'(\s+)# Create a mock file object with invalid type\n(\s+)mock_file\.filename',
        r'\1# Create a mock file object with invalid type\n\1mock_file = Mock(spec=UploadFile)\n\2mock_file.filename',
        content
    )
    
    # Fix missing is_valid definition
    content = re.sub(
        r'(\s+)# Test validation\n(\s+)assert not is_valid',
        r'\1# Test validation\n\1is_valid = mock_file.filename.endswith((".csv", ".xlsx", ".txt"))\n\2assert not is_valid',
        content
    )
    
    # Fix missing mock_file in process_file_success
    content = re.sub(
        r'(\s+)# Create a mock file object\n(\s+)mock_file\.filename',
        r'\1# Create a mock file object\n\1mock_file = Mock(spec=UploadFile)\n\2mock_file.filename',
        content
    )
    
    # Fix UserData instantiation issues
    content = re.sub(
        r'user_data = UserData\(\n\s+user_id=mock_user_id,',
        r'user_data = UserData(\n                user_id=mock_user_id,',
        content
    )
    
    # Fix the duplicate SchemaField lines
    content = re.sub(
        r'(\s+)SchemaField\(\n(\s+)SchemaField\(',
        r'\1SchemaField(',
        content
    )
    
    # Fix missing data_schema field definitions
    content = re.sub(
        r'is_high_cardinality=False,\n\s+original_filename="test\.csv"\n\s+\),\n\s+SchemaField\(\n\s+SchemaField\(',
        r'is_high_cardinality=False\n                    )',
        content
    )
    
    # Fix empty data initialization
    content = re.sub(
        r'(\s+)# Create empty dataframe\n\n(\s+)# Create a mock file object',
        r'\1# Create empty dataframe\n\1data = pd.DataFrame()\n\n\2# Create a mock file object',
        content
    )
    
    # Fix process_file_empty_data mock_file
    content = re.sub(
        r'(\s+)# Create a mock file object\n(\s+)mock_file\.filename = "test\.csv"',
        r'\1# Create a mock file object\n\1mock_file = Mock(spec=UploadFile)\n\2mock_file.filename = "test.csv"',
        content
    )
    
    # Fix missing UserData creation
    content = re.sub(
        r'with patch\("app\.utils\.schema_inference\.infer_schema", return_value=\[\]\):\n(\s+)# Create UserData object\n(\s+)s3_url=',
        r'with patch("app.utils.schema_inference.infer_schema", return_value=[]):\n\1# Create UserData object\n\1user_data = UserData(\n\1    user_id=mock_user_id,\n\1    filename=mock_file.filename,\n\1    original_filename="test.csv",\n\1    num_rows=0,\n\1    num_columns=0,\n\2s3_url=',
        content
    )
    
    # Fix incomplete UserData creation in test_process_file_invalid_data
    content = re.sub(
        r'# Create invalid data \(non-serializable\)\n\n(\s+)# Create a mock file object',
        r'# Create invalid data (non-serializable)\n    data = pd.DataFrame({"invalid": [object()]})\n\n\1# Create a mock file object',
        content
    )
    
    content = re.sub(
        r'(\s+)# Create a mock file object\n(\s+)mock_file\.filename = "test\.csv"\n(\s+)mock_file\.content_type',
        r'\1# Create a mock file object\n\1mock_file = Mock(spec=UploadFile)\n\2mock_file.filename = "test.csv"\n\3mock_file.content_type',
        content
    )
    
    # Fix missing UserData in invalid data test
    content = re.sub(
        r'"app\.utils\.schema_inference\.infer_schema",\n(\s+)SchemaField\(',
        r'"app.utils.schema_inference.infer_schema",\n            return_value=[\n\1SchemaField(',
        content
    )
    
    content = re.sub(
        r'(\s+)\]\):\n(\s+)# Create UserData object\n(\s+)s3_url=',
        r'\1]):\n\2# Create UserData object\n\2user_data = UserData(\n\2    user_id=mock_user_id,\n\2    filename=mock_file.filename,\n\2    original_filename="test.csv",\n\2    num_rows=3,\n\2    num_columns=1,\n\3s3_url=',
        content
    )
    
    # Fix SchemaField creation
    content = re.sub(
        r'(\s+)SchemaField\(\n(\s+)\)\n(\s+)\),',
        r'\1SchemaField(\n\1    field_name="invalid",\n\1    field_type="text",\n\1    data_type="object",\n\1    inferred_dtype="object",\n\1    unique_values=1,\n\1    missing_values=0,\n\1    example_values=[],\n\1    is_constant=False,\n\1    is_high_cardinality=False\n\2)',
        content
    )
    
    # Remove "No newline at end of file"
    content = content.replace(' No newline at end of file', '')
    
    # Fix trailing issues
    if not content.endswith('\n'):
        content += '\n'
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_user_data():
    """Fix test_user_data.py"""
    file_path = "tests/test_models/test_user_data.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing variable definitions in test_ai_summary_creation
    content = re.sub(
        r'def test_ai_summary_creation\(\):\n(\s+)"""Test creating an AISummary instance."""\n(\s+)ai_summary = AISummary\(',
        r'def test_ai_summary_creation():\n\1"""Test creating an AISummary instance."""\n\1current_time = get_current_time()\n\2ai_summary = AISummary(',
        content
    )
    
    # Fix missing variable definitions in test_user_data_creation
    content = re.sub(
        r'def test_user_data_creation\(\):\n(\s+)"""Test creating a UserData instance."""\n\n\n(\s+)user_data = UserData\(',
        r'def test_user_data_creation():\n\1"""Test creating a UserData instance."""\n\1current_time = get_current_time()\n\1schema_field = SchemaField(\n\1    field_name="test_column",\n\1    field_type="numeric",\n\1    data_type="float",\n\1    inferred_dtype="float64",\n\1    unique_values=100,\n\1    missing_values=5,\n\1    example_values=[1.0, 2.0, 3.0],\n\1    is_constant=False,\n\1    is_high_cardinality=True\n\1)\n\1ai_summary = AISummary(\n\1    overview="Test overview",\n\1    issues=["Issue 1", "Issue 2"],\n\1    relationships=["Relationship 1", "Relationship 2"],\n\1    suggestions=["Suggestion 1", "Suggestion 2"],\n\1    rawMarkdown="# Test Analysis\\n\\nThis is a test analysis.",\n\1    createdAt=current_time\n\1)\n\n\2user_data = UserData(',
        content
    )
    
    # Fix missing UserData instantiation in test_user_data_optional_ai_summary
    content = re.sub(
        r'def test_user_data_optional_ai_summary\(\):\n(\s+)"""Test that UserData can be created without an AI summary."""\n(\s+)s3_url=',
        r'def test_user_data_optional_ai_summary():\n\1"""Test that UserData can be created without an AI summary."""\n\1user_data = UserData(\n\1    user_id="test_user",\n\1    filename="test.csv",\n\1    original_filename="test.csv",\n\1    num_rows=100,\n\1    num_columns=1,\n\2s3_url=',
        content
    )
    
    # Fix incomplete SchemaField creation in test_schema_field_with_different_data_types
    content = re.sub(
        r'# Test with numeric data\n(\s+)numeric_field = SchemaField\(\n(\s+)assert numeric_field\.field_type',
        r'# Test with numeric data\n\1numeric_field = SchemaField(\n\1    field_name="numeric",\n\1    field_type="numeric",\n\1    data_type="float",\n\1    inferred_dtype="float64",\n\1    unique_values=10,\n\1    missing_values=0,\n\1    example_values=[1.0, 2.0],\n\1    is_constant=False,\n\1    is_high_cardinality=False\n\1)\n\2assert numeric_field.field_type',
        content
    )
    
    # Fix categorical field
    content = re.sub(
        r'# Test with categorical data\n(\s+)categorical_field = SchemaField\(\n(\s+)assert categorical_field\.field_type',
        r'# Test with categorical data\n\1categorical_field = SchemaField(\n\1    field_name="category",\n\1    field_type="categorical",\n\1    data_type="string",\n\1    inferred_dtype="object",\n\1    unique_values=5,\n\1    missing_values=0,\n\1    example_values=["A", "B"],\n\1    is_constant=False,\n\1    is_high_cardinality=False\n\1)\n\2assert categorical_field.field_type',
        content
    )
    
    # Fix datetime field
    content = re.sub(
        r'# Test with datetime data\n(\s+)datetime_field = SchemaField\(\n(\s+)assert datetime_field\.field_type',
        r'# Test with datetime data\n\1datetime_field = SchemaField(\n\1    field_name="date",\n\1    field_type="datetime",\n\1    data_type="datetime",\n\1    inferred_dtype="datetime64[ns]",\n\1    unique_values=30,\n\1    missing_values=0,\n\1    example_values=["2024-01-01"],\n\1    is_constant=False,\n\1    is_high_cardinality=True\n\1)\n\2assert datetime_field.field_type',
        content
    )
    
    # Fix UserData validation tests
    content = re.sub(
        r'UserData\(\n(\s+)# Empty user_id\n(\s+)filename=',
        r'UserData(\n\1user_id="",  # Empty user_id\n\2filename=',
        content
    )
    
    content = re.sub(
        r'UserData\(\n(\s+)s3_url="invalid_url",\n(\s+)# Invalid URL\n(\s+)num_rows=',
        r'UserData(\n\1user_id="test_user",\n\1filename="test.csv",\n\1original_filename="test.csv",\n\1s3_url="invalid_url",  # Invalid URL\n\3num_rows=',
        content
    )
    
    content = re.sub(
        r'UserData\(\n(\s+)s3_url="https://example\.com/test\.csv",\n(\s+)# Negative number of rows\n(\s+)num_columns=',
        r'UserData(\n\1user_id="test_user",\n\1filename="test.csv",\n\1original_filename="test.csv",\n\1s3_url="https://example.com/test.csv",\n\1num_rows=-1,  # Negative number of rows\n\3num_columns=',
        content
    )
    
    # Remove "No newline at end of file"
    content = content.replace(' No newline at end of file', '')
    
    # Ensure file ends with newline
    if not content.endswith('\n'):
        content += '\n'
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def main():
    """Run all fixes"""
    print("Applying final syntax fixes...")
    
    fix_visualization_endpoints()
    fix_full_workflow()
    fix_data_processing()
    fix_model_training()
    fix_upload()
    fix_user_data()
    
    print("\n✅ All files fixed!")

if __name__ == "__main__":
    main()