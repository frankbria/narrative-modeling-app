#!/usr/bin/env python3
"""
Fix all test files to use proper authentication fixtures
"""
import os
import re
from pathlib import Path

def fix_auth_in_file(content):
    """Fix authentication issues in test content"""
    
    # Replace async_test_client with async_authorized_client in test functions
    content = re.sub(
        r'async_test_client(?=\s*[,\)])',
        'async_authorized_client',
        content
    )
    
    # Replace client with authorized_client in sync tests
    content = re.sub(
        r'def test_.*\(.*\bclient\b',
        lambda m: m.group(0).replace('client', 'authorized_client'),
        content
    )
    
    # Remove direct TestClient instantiation
    if 'client = TestClient(app)' in content:
        content = content.replace('client = TestClient(app)', '# Use authorized_client fixture instead')
    
    return content

def main():
    """Fix all test files"""
    
    test_dir = Path("tests")
    
    # Find all test files
    for test_file in test_dir.rglob("test_*.py"):
        if test_file.name == "test_utils.py":
            continue
            
        print(f"Processing {test_file}")
        
        with open(test_file, 'r') as f:
            content = f.read()
        
        original = content
        content = fix_auth_in_file(content)
        
        if content != original:
            with open(test_file, 'w') as f:
                f.write(content)
            print(f"  ✅ Fixed {test_file}")
        else:
            print(f"  ⏭️  No auth changes needed for {test_file}")

if __name__ == "__main__":
    main()