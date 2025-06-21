#!/usr/bin/env python3
"""
Fix hardcoded file IDs in test_visualization_endpoints.py
"""
import re

def fix_hardcoded_ids():
    """Replace hardcoded test-file-123 with mock_user_data.id"""
    file_path = "tests/test_api/test_visualization_endpoints.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace all occurrences of test-file-123 with {mock_user_data.id}
    content = re.sub(r'"/api/v1/visualizations/([^/]+)/test-file-123', r'f"/api/v1/visualizations/\1/{mock_user_data.id}', content)
    
    # Fix the ones that already have f-strings but still use test-file-123
    content = re.sub(r'f"/api/v1/visualizations/([^/]+)/test-file-123', r'f"/api/v1/visualizations/\1/{mock_user_data.id}', content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed hardcoded IDs in {file_path}")

if __name__ == "__main__":
    fix_hardcoded_ids()