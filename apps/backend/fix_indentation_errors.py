#!/usr/bin/env python3
"""
Fix remaining indentation and syntax errors
"""
import re

def fix_full_workflow():
    """Fix test_full_workflow.py indentation issues"""
    file_path = "tests/integration/test_full_workflow.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the correlation test indentation
    content = re.sub(
        r'(\s+)"matrix": \[\[1\.0, 0\.3\], \[0\.3, 1\.0\]\]\n\n(\s+)\}\n\n(\s+)\n\n(\s+)response = await async_authorized_client\.get',
        r'\1"matrix": [[1.0, 0.3], [0.3, 1.0]]\n\1}\n\1\n\1response = await async_authorized_client.get',
        content
    )
    
    # Fix UserData missing fields in PII detection test
    content = re.sub(
        r'with patch\(\'app\.models\.user_data\.UserData\.insert\', new_callable=AsyncMock\) as mock_insert:\n(\s+)s3_url="s3://test-bucket/test-file\.csv",\n(\s+)data_schema=\[\]\n(\s+),',
        r'with patch(\'app.models.user_data.UserData.insert\', new_callable=AsyncMock) as mock_insert:\n\1mock_user_data = UserData(\n\1    id=PydanticObjectId(),\n\1    user_id="test_user_123",\n\1    filename="pii.csv",\n\1    original_filename="pii.csv",\n\1    s3_url="s3://test-bucket/test-file.csv",\n\1    num_rows=2,\n\1    num_columns=4,\n\1    data_schema=[],',
        content
    )
    
    # Fix missing upload response
    content = re.sub(
        r'# Upload should detect PII\n(\s+)\n(\s+)assert response\.status_code == 200',
        r'# Upload should detect PII\n\1files = {\'file\': (\'pii.csv\', csv_content, \'text/csv\')}\n\1response = authorized_client.post("/api/v1/upload", files=files)\n\1\n\1assert response.status_code == 200',
        content
    )
    
    # Remove extra blank lines and fix indentation
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip excessive blank lines
        if line.strip() == '' and i + 1 < len(lines) and lines[i + 1].strip() == '':
            # Skip this blank line if the next is also blank
            i += 1
            continue
        fixed_lines.append(line)
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    # Remove "No newline at end of file"
    content = content.replace(' No newline at end of file', '')
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_data_processing():
    """Fix test_data_processing.py issues"""
    file_path = "tests/test_api/test_data_processing.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove duplicate mock_user_data creation
    content = re.sub(
        r'mock_user_data = create_mock_user_data\(\)\n(\s+)\n(\s+)mock_user_data = create_mock_user_data\(schema=schema_data, is_processed=True\)',
        r'mock_user_data = create_mock_user_data()',
        content
    )
    
    # Fix missing schema_data definitions
    content = re.sub(
        r'mock_user_data = create_mock_user_data\(schema=schema_data, is_processed=True\)\n(\s+)\n(\s+)with patch\(\'app\.models\.user_data\.UserData\.find_one\'',
        r'schema_data = {\n        "row_count": 5,\n        "column_count": 6,\n        "columns": [\n            {"name": "id", "type": "integer", "nullable": False},\n            {"name": "name", "type": "string", "nullable": False},\n            {"name": "age", "type": "integer", "nullable": False},\n            {"name": "salary", "type": "float", "nullable": False},\n            {"name": "email", "type": "email", "nullable": False},\n            {"name": "join_date", "type": "datetime", "nullable": False}\n        ]\n    }\n    \n    mock_user_data = create_mock_user_data(schema=schema_data, is_processed=True)\n\1\n\2with patch(\'app.models.user_data.UserData.find_one\'',
        content
    )
    
    # Fix test method signatures to use authorized client
    content = re.sub(
        r'async def test_[^(]+\(self, async_test_client: AsyncClient',
        r'async def test_\g<0>(self, async_authorized_client',
        content
    )
    
    # Replace async_test_client with async_authorized_client
    content = content.replace('async_test_client', 'async_authorized_client')
    
    # Fix double response assignments and blank lines
    content = re.sub(
        r'assert response\.status_code == 200\n(\s+)\n(\s+)data = response\.json\(\)\n(\s+)\n(\s+)# Check',
        r'assert response.status_code == 200\n\1data = response.json()\n\1\n\1# Check',
        content
    )
    
    # Remove duplicate response lines
    content = re.sub(
        r'response = await async_authorized_client\.[^(]+\([^)]+\)\n\s+\n\s+response = await async_authorized_client\.get\("/api/v1/data/test-file-123/schema"\)',
        r'response = await async_authorized_client.get("/api/v1/data/test-file-123/schema")',
        content
    )
    
    # Remove excessive blank lines
    content = re.sub(r'\n\s*\n\s*\n\s*\n', '\n\n', content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_model_training():
    """Fix test_model_training.py issues"""
    file_path = "tests/test_api/test_model_training.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing closing parentheses and response assignments
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/predict",\n\n(\s+)\n(\s+)json=request_data\n(\s+)\)',
        r'\1"/api/v1/ml/model_123/predict",\n\1json=request_data\n\1)',
        content
    )
    
    # Add missing response variable for predict endpoint
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/predict",\n(\s+)json=request_data\n(\s+)\)\n(\s+)\n(\s+)data = response\.json\(\)',
        r'\1"/api/v1/ml/model_123/predict",\n\2json=request_data\n\3)\n\4\n\4response = await async_authorized_client.post(\n\4    "/api/v1/ml/model_123/predict",\n\4    json=request_data\n\4)\n\5data = response.json()',
        content
    )
    
    # Fix deactivate endpoint
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/deactivate"\n(\s+)\)\n(\s+)\n(\s+)data = response\.json\(\)',
        r'\1"/api/v1/ml/model_123/deactivate"\n\2)\n\3\n\3response = await async_authorized_client.put(\n\3    "/api/v1/ml/model_123/deactivate"\n\3)\n\4data = response.json()',
        content
    )
    
    # Fix train endpoint response
    content = re.sub(
        r'(\s+)"/api/v1/ml/train",\n(\s+)json=request_data\n(\s+)\)\n(\s+)\n(\s+)assert response\.status_code',
        r'\1"/api/v1/ml/train",\n\2json=request_data\n\3)\n\4\n\4response = await async_authorized_client.post(\n\4    "/api/v1/ml/train",\n\4    json=request_data\n\4)\n\4\n\5assert response.status_code',
        content
    )
    
    # Fix missing request_data in predict_model_not_found
    content = re.sub(
        r'(\s+)"data": \[\{"feature1": 1\.0\}\]\n(\s+)\}',
        r'\1"data": [{"feature1": 1.0}]\n\2}\n\2\n\2request_data = {\n\2    "data": [{"feature1": 1.0}]\n\2}',
        content
    )
    
    # Fix delete endpoint to use DELETE method
    content = re.sub(
        r'response = await async_authorized_client\.get\(\n(\s+)"/api/v1/ml/model_123"\n(\s+)\)\n(\s+)data = response\.json\(\)\n(\s+)\n(\s+)assert response\.status_code == 200\n(\s+)assert "message" in data\n(\s+)assert "deleted successfully"',
        r'response = await async_authorized_client.delete(\n\1"/api/v1/ml/model_123"\n\2)\n\3data = response.json()\n\4\n\5assert response.status_code == 200\n\6assert "message" in data\n\7assert "deleted successfully"',
        content
    )
    
    # Replace mock_async_client with async_authorized_client
    content = content.replace('mock_async_client', 'async_authorized_client')
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_upload():
    """Fix test_upload.py issues"""
    file_path = "tests/test_api/test_upload.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix incomplete with statements
    content = re.sub(
        r'with patch\(\n(\s+)"app\.utils\.s3\.upload_file_to_s3",\n(\s+)# Mock schema inference',
        r'with patch(\n\1"app.utils.s3.upload_file_to_s3",\n\1return_value=(True, "https://test-bucket.s3.amazonaws.com/test.csv")):\n\2# Mock schema inference',
        content
    )
    
    # Fix SchemaField instantiation issues
    content = re.sub(
        r'(\s+)SchemaField\(\n(\s+)\),',
        r'\1SchemaField(\n\1    field_name="invalid",\n\1    field_type="text",\n\1    data_type="object",\n\1    inferred_dtype="object",\n\1    unique_values=1,\n\1    missing_values=0,\n\1    example_values=[],\n\1    is_constant=False,\n\1    is_high_cardinality=False\n\2)',
        content
    )
    
    # Fix UserData instantiation indentation
    content = re.sub(
        r'# Create UserData object\n(\s+)user_data = UserData\(\n(\s+)user_id=',
        r'# Create UserData object\n\1user_data = UserData(\n\1    user_id=',
        content
    )
    
    # Fix misaligned fields
    content = re.sub(
        r'(\s+)is_high_cardinality=False,\n(\s+)original_filename="test\.csv"\n(\s+)\),\n(\s+)SchemaField\(',
        r'\1is_high_cardinality=False\n\1)\n\1],\n\1original_filename="test.csv"\n\1)',
        content
    )
    
    # Clean up data_schema structure
    content = re.sub(
        r'data_schema=\[\n(\s+)SchemaField\(\n([^]]+)\n(\s+)\]\)',
        lambda m: 'data_schema=[\n' + m.group(1) + 'SchemaField(\n' + clean_schema_field(m.group(2)) + '\n' + m.group(3) + ']',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def clean_schema_field(field_content):
    """Clean up SchemaField content"""
    # Remove duplicate SchemaField declarations
    field_content = re.sub(r'\n\s+SchemaField\(\n', '\n', field_content)
    # Ensure proper closing
    if not field_content.strip().endswith(')'):
        field_content = field_content.rstrip() + '\n                )'
    return field_content

def fix_visualization_endpoints():
    """Fix test_visualization_endpoints.py issues"""
    file_path = "tests/test_api/test_visualization_endpoints.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove duplicate csv_buffer lines
    content = re.sub(
        r'csv_buffer = io\.BytesIO\(\)\n(\s+)csv_buffer = io\.BytesIO\(\)\n',
        r'csv_buffer = io.BytesIO()\n',
        content
    )
    
    # Fix missing data = response.json() lines
    content = re.sub(
        r'assert response\.status_code == 200\n(\s+)assert "data" in data',
        r'assert response.status_code == 200\n\1data = response.json()\n\1assert "data" in data',
        content
    )
    
    content = re.sub(
        r'assert response\.status_code == 200\n(\s+)assert "timestamps" in data',
        r'assert response.status_code == 200\n\1data = response.json()\n\1assert "timestamps" in data',
        content
    )
    
    # Fix malformed response lines
    content = re.sub(
        r'(\s+)response = authorized_client\.get\(\n\n(\s+)f"/api/v1/visualizations/([^"]+)"\n\n(\s+)\)',
        r'\1response = authorized_client.get(\n\1    f"/api/v1/visualizations/\3"\n\1)',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def main():
    """Run all fixes"""
    print("Fixing remaining indentation and syntax errors...")
    
    fix_full_workflow()
    fix_data_processing()
    fix_model_training()
    fix_upload()
    fix_visualization_endpoints()
    
    print("\n✅ All files fixed!")

if __name__ == "__main__":
    main()