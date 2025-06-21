#!/usr/bin/env python3
"""
Final comprehensive syntax fixes
"""
import re

def fix_data_processing():
    """Fix test_data_processing.py duplicate method definitions"""
    file_path = "tests/test_api/test_data_processing.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix duplicate async def test_ definitions
    content = re.sub(
        r'async def test_async def test_([^(]+)\(self, async_authorized_client: AsyncClient\(',
        r'async def test_\1(self, async_authorized_client',
        content
    )
    
    # Fix missing schema_data definitions
    # Add schema_data before methods that reference it
    methods_needing_schema = [
        'test_get_schema_success',
        'test_get_statistics_success', 
        'test_get_quality_report_success',
        'test_get_data_preview_success',
        'test_export_data_csv',
        'test_process_dataset_with_invalid_file'
    ]
    
    for method in methods_needing_schema:
        # Add schema_data definition at the start of each method that needs it
        pattern = f'(async def {method}[^:]+:\\s*\n\\s*"""[^"]+"""\\s*\n)'
        replacement = r'\1    schema_data = {\n        "row_count": 5,\n        "column_count": 6,\n        "columns": [\n            {"name": "id", "type": "integer", "nullable": False},\n            {"name": "name", "type": "string", "nullable": False},\n            {"name": "age", "type": "integer", "nullable": False},\n            {"name": "salary", "type": "float", "nullable": False},\n            {"name": "email", "type": "email", "nullable": False},\n            {"name": "join_date", "type": "datetime", "nullable": False}\n        ]\n    }\n    \n'
        content = re.sub(pattern, replacement, content)
    
    # Fix wrong endpoint calls in export and preview tests
    content = re.sub(
        r'response = await async_authorized_client\.get\("/api/v1/data/test-file-123/schema"\)\s*\n\s*assert response\.status_code == 200\s*\n\s*data = response\.json\(\)\s*\n\s*assert "data" in data',
        r'response = await async_authorized_client.get("/api/v1/data/test-file-123/preview?limit=3")\n        \n        assert response.status_code == 200\n        data = response.json()\n        assert "data" in data',
        content
    )
    
    content = re.sub(
        r'response = await async_authorized_client\.get\("/api/v1/data/test-file-123/schema"\)\s*\n\s*assert response\.status_code == 200\s*\n\s*data = response\.json\(\)\s*\n\s*assert "download_url" in data',
        r'response = await async_authorized_client.post(\n            "/api/v1/data/test-file-123/export",\n            json={"format": "csv"}\n        )\n        \n        assert response.status_code == 200\n        data = response.json()\n        assert "download_url" in data',
        content
    )
    
    # Remove duplicate response assignments
    content = re.sub(
        r'response = await async_authorized_client\.post\(\n\s+"/api/v1/data/process",\n\s+json=\{"file_id": "test-file-123"\}\n\s+\)\s*\n\s*[^\n]+\n\s*[^\n]+\n\s*[^\n]+\n\s*[^\n]+\n\s*[^\n]+\n\s*response = await async_authorized_client',
        r'response = await async_authorized_client.post(\n            "/api/v1/data/process",\n            json={"file_id": "test-file-123"}\n        )\n        \n        assert response.status_code == 200\n        data = response.json()',
        content
    )
    
    # Clean up excessive blank lines
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_model_training():
    """Fix test_model_training.py issues"""
    file_path = "tests/test_api/test_model_training.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove orphaned lines
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/predict",\n\n(\s+)\n(\s+)json=request_data\n\n(\s+)\n(\s+)\)\n(\s+)\n(\s+)response =',
        r'',
        content
    )
    
    content = re.sub(
        r'(\s+)"/api/v1/ml/model_123/deactivate"\n(\s+)\)\n(\s+)\n(\s+)response =',
        r'',
        content
    )
    
    content = re.sub(
        r'(\s+)"/api/v1/ml/train",\n(\s+)json=request_data\n(\s+)\)\n(\s+)\n(\s+)response =',
        r'',
        content
    )
    
    content = re.sub(
        r'(\s+)"data": \[\{"feature1": 1\.0\}\]\n(\s+)\}\n(\s+)\n(\s+)request_data =',
        r'',
        content
    )
    
    # Fix response assignments
    content = re.sub(
        r'response = await async_authorized_client\.get\(\n(\s+)"/api/v1/ml/model_123"\n(\s+)\)\n(\s+)data = response\.json\(\)\n(\s+)\n(\s+)assert response\.status_code == 200',
        r'response = await async_authorized_client.get(\n\1"/api/v1/ml/model_123"\n\2)\n\3\n\3assert response.status_code == 200\n\3data = response.json()',
        content
    )
    
    content = re.sub(
        r'response = await async_authorized_client\.delete\(\n(\s+)"/api/v1/ml/model_123"\n(\s+)\)\n(\s+)data = response\.json\(\)\n(\s+)\n(\s+)assert response\.status_code == 200',
        r'response = await async_authorized_client.delete(\n\1"/api/v1/ml/model_123"\n\2)\n\3\n\3assert response.status_code == 200\n\3data = response.json()',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_visualization_endpoints():
    """Fix test_visualization_endpoints.py issues"""
    file_path = "tests/test_api/test_visualization_endpoints.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix malformed response lines
    content = re.sub(
        r'(\s+)response = authorized_client\.get\(\n\n(\s+)f"/api/v1/visualizations/',
        r'\1response = authorized_client.get(\n\1    f"/api/v1/visualizations/',
        content
    )
    
    # Remove duplicate blank lines
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    # Fix missing data = response.json()
    content = re.sub(
        r'assert response\.status_code == 200\n(\s+)data = response\.json\(\)\n(\s+)assert "data" in data',
        r'assert response.status_code == 200\n\1data = response.json()\n\2assert "data" in data',
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_full_workflow():
    """Fix test_full_workflow.py issues"""
    file_path = "tests/integration/test_full_workflow.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove "No newline at end of file" in the middle
    content = re.sub(r' No newline at end of file\n', '\n', content)
    
    # Fix excessive blank lines
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    # Fix indentation issues
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Fix indentation for specific problematic lines
        if 'response = await async_authorized_client' in line and line.startswith('                        '):
            line = '                    ' + line.strip()
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_upload():
    """Fix test_upload.py issues"""
    file_path = "tests/test_api/test_upload.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix SchemaField closing parentheses
    content = re.sub(
        r'(\s+)is_high_cardinality=False\n\n(\s+)\)\n\n(\s+)\],\n\n(\s+)original_filename="test\.csv"\n\n(\s+)\)',
        r'\1is_high_cardinality=False\n\1)\n\1],\n\1original_filename="test.csv"\n\1)',
        content
    )
    
    # Fix blank lines in SchemaField definitions
    content = re.sub(
        r'SchemaField\(\n\n(\s+)field_name=',
        r'SchemaField(\n\1field_name=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)field_type=',
        r',\n\1field_type=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)data_type=',
        r',\n\1data_type=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)inferred_dtype=',
        r',\n\1inferred_dtype=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)unique_values=',
        r',\n\1unique_values=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)missing_values=',
        r',\n\1missing_values=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)example_values=',
        r',\n\1example_values=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)is_constant=',
        r',\n\1is_constant=',
        content
    )
    
    content = re.sub(
        r',\n\n(\s+)is_high_cardinality=',
        r',\n\1is_high_cardinality=',
        content
    )
    
    # Remove excessive blank lines
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def main():
    """Run all fixes"""
    print("Applying final comprehensive syntax fixes...")
    
    fix_data_processing()
    fix_model_training()
    fix_visualization_endpoints()
    fix_full_workflow()
    fix_upload()
    
    print("\n✅ All files fixed!")

if __name__ == "__main__":
    main()