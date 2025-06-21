#!/usr/bin/env python3
"""
Fix remaining test issues in the backend test suite
"""
import re
import os

def fix_visualization_endpoints():
    """Fix test_visualization_endpoints.py"""
    file_path = "tests/test_api/test_visualization_endpoints.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing response = lines
    fixes = [
        # Line 91-92
        ('response = authorized_client.get("/api/v1/visualizations/boxplot/test-file-123/value")\n                \n                assert response.status_code == 200',
         'response = authorized_client.get("/api/v1/visualizations/boxplot/test-file-123/value")\n                \n                assert response.status_code == 200'),
        
        # Line 113
        ('response = authorized_client.get("/api/v1/visualizations/correlation/test-file-123")\n                \n                assert response.status_code == 200',
         'response = authorized_client.get("/api/v1/visualizations/correlation/test-file-123")\n                \n                assert response.status_code == 200'),
        
        # Line 132
        ('response = authorized_client.get("/api/v1/visualizations/scatter/test-file-123/price/quantity")\n                \n                assert response.status_code == 200',
         'response = authorized_client.get("/api/v1/visualizations/scatter/test-file-123/price/quantity")\n                \n                assert response.status_code == 200'),
        
        # Line 147
        ('with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                sample_dataframe.to_csv(csv_buffer, index=False)',
         'with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                csv_buffer = io.BytesIO()\n                sample_dataframe.to_csv(csv_buffer, index=False)'),
        
        # Line 152
        ('filters = \'[{"column": "category", "operator": "equals", "value": "A"}]\'\n                    f"/api/v1/visualizations/scatter/test-file-123/price/quantity?filters={filters}"',
         'filters = \'[{"column": "category", "operator": "equals", "value": "A"}]\'\n                response = authorized_client.get(\n                    f"/api/v1/visualizations/scatter/test-file-123/price/quantity?filters={filters}"'),
        
        # Line 166
        ('with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                sample_dataframe.to_csv(csv_buffer, index=False)',
         'with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                csv_buffer = io.BytesIO()\n                sample_dataframe.to_csv(csv_buffer, index=False)'),
        
        # Line 170
        ('mock_s3.return_value = csv_buffer\n                \n                    "/api/v1/visualizations/line/test-file-123/date?y_columns=value,price"',
         'mock_s3.return_value = csv_buffer\n                \n                response = authorized_client.get(\n                    "/api/v1/visualizations/line/test-file-123/date?y_columns=value,price"'),
        
        # Line 187
        ('with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                sample_dataframe.to_csv(csv_buffer, index=False)',
         'with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                csv_buffer = io.BytesIO()\n                sample_dataframe.to_csv(csv_buffer, index=False)'),
        
        # Line 191
        ('mock_s3.return_value = csv_buffer\n                \n                    "/api/v1/visualizations/timeseries/test-file-123/date/value"',
         'mock_s3.return_value = csv_buffer\n                \n                response = authorized_client.get(\n                    "/api/v1/visualizations/timeseries/test-file-123/date/value"'),
        
        # Line 208
        ('with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                sample_dataframe.to_csv(csv_buffer, index=False)',
         'with patch(\'app.utils.s3.get_file_from_s3\') as mock_s3:\n                csv_buffer = io.BytesIO()\n                sample_dataframe.to_csv(csv_buffer, index=False)'),
        
        # Line 212
        ('mock_s3.return_value = csv_buffer\n                \n                    "/api/v1/visualizations/scatter/test-file-123/nonexistent/value"',
         'mock_s3.return_value = csv_buffer\n                \n                response = authorized_client.get(\n                    "/api/v1/visualizations/scatter/test-file-123/nonexistent/value"'),
    ]
    
    for old, new in fixes:
        if old in content:
            content = content.replace(old, new)
    
    # Add missing data = response.json() lines
    missing_data_fixes = [
        ('assert response.status_code == 200\n                assert data["min"]',
         'assert response.status_code == 200\n                data = response.json()\n                assert data["min"]'),
        
        ('assert response.status_code == 200\n                assert "columns" in data',
         'assert response.status_code == 200\n                data = response.json()\n                assert "columns" in data'),
        
        ('assert response.status_code == 200\n                assert "data" in data',
         'assert response.status_code == 200\n                data = response.json()\n                assert "data" in data'),
        
        ('assert response.status_code == 200\n                assert "data" in data\n                assert len(data["data"]) < 100',
         'assert response.status_code == 200\n                data = response.json()\n                assert "data" in data\n                assert len(data["data"]) < 100'),
        
        ('assert response.status_code == 200\n                assert "data" in data\n                assert "lines" in data',
         'assert response.status_code == 200\n                data = response.json()\n                assert "data" in data\n                assert "lines" in data'),
        
        ('assert response.status_code == 200\n                assert "timestamps" in data',
         'assert response.status_code == 200\n                data = response.json()\n                assert "timestamps" in data'),
    ]
    
    for old, new in missing_data_fixes:
        if old in content:
            content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_documentation_tests():
    """Fix test_documentation.py"""
    file_path = "tests/test_api/test_documentation.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace all client. with authorized_client.
    content = re.sub(r'\bclient\.', 'authorized_client.', content)
    
    # Fix the fixture parameters
    content = content.replace(
        'def test_get_client_libraries_success(\n        self, \n        mock_doc_service_class, \n        client, \n        mock_client_libraries\n    ):',
        'def test_get_client_libraries_success(\n        self, \n        mock_doc_service_class, \n        authorized_client, \n        mock_client_libraries\n    ):'
    )
    
    content = content.replace(
        'def test_get_integration_examples_success(\n        self, \n        mock_doc_service_class, \n        client, \n        mock_integration_examples\n    ):',
        'def test_get_integration_examples_success(\n        self, \n        mock_doc_service_class, \n        authorized_client, \n        mock_integration_examples\n    ):'
    )
    
    content = content.replace(
        'def test_get_postman_collection_success(\n        self, \n        mock_doc_service_class, \n        client, \n        mock_postman_collection\n    ):',
        'def test_get_postman_collection_success(\n        self, \n        mock_doc_service_class, \n        authorized_client, \n        mock_postman_collection\n    ):'
    )
    
    # Remove the client fixture definition
    content = re.sub(
        r'@pytest\.fixture\s*\ndef\s+client\(\):\s*\n.*?"Use authorized_client fixture instead".*?\n.*?yield client.*?\n.*?app\.dependency_overrides\.pop\(get_current_user_id, None\)\s*\n',
        '',
        content,
        flags=re.DOTALL
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_onboarding_tests():
    """Fix test_onboarding.py"""
    file_path = "tests/test_api/test_onboarding.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace all client. with authorized_client.
    content = re.sub(r'\bclient\.', 'authorized_client.', content)
    
    # Fix the fixture parameters
    content = content.replace(
        'def test_get_onboarding_status_success(\n        self, \n        mock_service_class, \n        client, \n        mock_onboarding_status\n    ):',
        'def test_get_onboarding_status_success(\n        self, \n        mock_service_class, \n        authorized_client, \n        mock_onboarding_status\n    ):'
    )
    
    content = content.replace(
        'def test_get_onboarding_steps_success(\n        self, \n        mock_service_class, \n        client, \n        mock_onboarding_steps\n    ):',
        'def test_get_onboarding_steps_success(\n        self, \n        mock_service_class, \n        authorized_client, \n        mock_onboarding_steps\n    ):'
    )
    
    content = content.replace(
        'def test_get_onboarding_step_success(\n        self, \n        mock_service_class, \n        client, \n        mock_onboarding_steps\n    ):',
        'def test_get_onboarding_step_success(\n        self, \n        mock_service_class, \n        authorized_client, \n        mock_onboarding_steps\n    ):'
    )
    
    content = content.replace(
        'def test_get_sample_datasets_success(\n        self, \n        mock_service_class, \n        client, \n        mock_sample_datasets\n    ):',
        'def test_get_sample_datasets_success(\n        self, \n        mock_service_class, \n        authorized_client, \n        mock_sample_datasets\n    ):'
    )
    
    # Remove the client fixture definition
    content = re.sub(
        r'@pytest\.fixture\s*\ndef\s+client\(\):\s*\n.*?"Use authorized_client fixture instead".*?\n.*?yield client.*?\n.*?app\.dependency_overrides\.pop\(get_current_user_id, None\)\s*\n',
        '',
        content,
        flags=re.DOTALL
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def fix_visualizations_tests():
    """Fix test_visualizations.py - uses async_test_client instead of async_authorized_client"""
    file_path = "tests/test_api/test_visualizations.py"
    print(f"Fixing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace all async_test_client with async_authorized_client
    content = content.replace('async_test_client', 'async_authorized_client')
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")

def main():
    """Main function to run all fixes"""
    print("Fixing remaining test issues...")
    
    fix_visualization_endpoints()
    fix_documentation_tests()
    fix_onboarding_tests()
    fix_visualizations_tests()
    
    print("\n✅ All test files fixed!")

if __name__ == "__main__":
    main()