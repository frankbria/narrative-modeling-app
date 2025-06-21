#!/usr/bin/env python3
"""
Script to fix all test issues related to UserData schema changes
"""
import os
import re
from pathlib import Path

def fix_user_data_instantiation(content):
    """Fix UserData instantiation with old schema"""
    
    # Pattern to match UserData instantiation
    user_data_pattern = r'UserData\s*\(\s*([^)]+)\)'
    
    def replace_user_data(match):
        args = match.group(1)
        
        # Check if it already has new fields
        if 'original_filename' in args and 's3_url' in args:
            return match.group(0)
        
        # Extract existing fields
        lines = []
        current_line = ""
        paren_depth = 0
        
        for char in args:
            current_line += char
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                lines.append(current_line.strip())
                current_line = ""
        
        if current_line.strip():
            lines.append(current_line.strip())
        
        # Process each field
        new_lines = []
        has_filename = False
        has_original_filename = False
        has_s3_url = False
        filename_value = '"test.csv"'
        
        for line in lines:
            # Skip old fields
            if any(old_field in line for old_field in ['file_path=', 'file_size=', 'file_type=', 'upload_date=']):
                # Extract filename from file_path if present
                if 'file_path=' in line:
                    path_match = re.search(r'file_path\s*=\s*["\']([^"\']+)["\']', line)
                    if path_match:
                        path = path_match.group(1)
                        filename_value = f'"{os.path.basename(path)}"'
                continue
            
            # Update is_processed to be part of the model
            if 'is_processed=' in line:
                new_lines.append(line)
            else:
                new_lines.append(line)
            
            # Check for existing fields
            if 'filename=' in line:
                has_filename = True
                filename_match = re.search(r'filename\s*=\s*["\']([^"\']+)["\']', line)
                if filename_match:
                    filename_value = f'"{filename_match.group(1)}"'
            if 'original_filename=' in line:
                has_original_filename = True
            if 's3_url=' in line:
                has_s3_url = True
        
        # Add missing required fields
        if has_filename and not has_original_filename:
            new_lines.append(f'original_filename={filename_value}')
        if not has_s3_url:
            new_lines.append('s3_url="s3://test-bucket/test-file.csv"')
        if not has_filename:
            new_lines.append(f'filename={filename_value}')
            new_lines.append(f'original_filename={filename_value}')
        
        # Ensure num_rows and num_columns exist
        has_num_rows = any('num_rows=' in line for line in new_lines)
        has_num_columns = any('num_columns=' in line for line in new_lines)
        
        if not has_num_rows:
            new_lines.append('num_rows=100')
        if not has_num_columns:
            new_lines.append('num_columns=5')
        
        # Ensure data_schema exists
        has_data_schema = any('data_schema=' in line for line in new_lines)
        if not has_data_schema:
            new_lines.append('data_schema=[]')
        
        # Join with proper formatting
        if len(new_lines) > 3:
            result = 'UserData(\n        ' + ',\n        '.join(new_lines) + '\n    )'
        else:
            result = 'UserData(' + ', '.join(new_lines) + ')'
        
        return result
    
    # Apply replacements
    content = re.sub(user_data_pattern, replace_user_data, content, flags=re.DOTALL)
    
    return content

def fix_mock_user_data_attributes(content):
    """Fix mock UserData attribute assignments"""
    
    # Replace old field assignments
    replacements = [
        (r'\.file_path\s*=', '.s3_url ='),
        (r'\.file_size\s*=', '.num_rows = 100  # Changed from file_size'),
        (r'\.file_type\s*=', '.data_schema = []  # Changed from file_type'),
        (r'\.upload_date\s*=', '.created_at ='),
    ]
    
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    return content

def fix_file(file_path):
    """Fix a single test file"""
    print(f"Processing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Apply fixes
    content = fix_user_data_instantiation(content)
    content = fix_mock_user_data_attributes(content)
    
    # Write back if changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Fixed {file_path}")
    else:
        print(f"  ⏭️  No changes needed for {file_path}")

def main():
    """Main function to fix all test files"""
    
    # Files identified as having UserData issues
    files_to_fix = [
        "tests/test_api/test_data_processing.py",
        "tests/test_api/test_model_training.py",
        "tests/test_api/test_upload.py",
        "tests/test_api/test_analytics.py",
        "tests/test_api/test_visualization_endpoints.py",
        "tests/test_services/test_visualization_cache.py",
        "tests/test_services/test_ai_summary.py",
        "tests/integration/test_full_workflow.py",
        "tests/test_processing/test_data_processor.py",
        "tests/test_models/test_user_data.py",
        "tests/test_security/test_upload_handler.py",
        "tests/test_security/test_monitoring.py",
    ]
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_file(file_path)
        else:
            print(f"  ❌ File not found: {file_path}")
    
    print("\nDone! Now run the tests to see if they pass.")

if __name__ == "__main__":
    main()