#!/usr/bin/env python3
"""
Fix syntax and indentation errors in test files
"""
import os
import re

def fix_syntax_errors(content):
    """Fix various syntax errors in the content"""
    
    # Fix double commas
    content = re.sub(r',,+', ',', content)
    
    # Fix trailing commas before closing parenthesis
    content = re.sub(r',\s*\)', ')', content)
    
    # Fix PydanticObjectId( without closing
    content = re.sub(r'PydanticObjectId\(\s*,', 'PydanticObjectId(),', content)
    
    # Fix datetime.now( without closing
    content = re.sub(r'datetime\.now\(\s*,', 'datetime.now(),', content)
    
    # Fix malformed UserData instantiations
    # Pattern to fix UserData with extra closing parenthesis and comma
    content = re.sub(
        r'UserData\(([\s\S]*?)\),\s*([a-zA-Z_]+\s*=)',
        r'UserData(\1,\n        \2',
        content
    )
    
    # Fix lines that have 'No newline at end of file' in the middle
    content = re.sub(r'\n\s*No newline at end of file\n', '\n', content)
    
    # Fix duplicate assignments
    lines = content.split('\n')
    seen_assignments = set()
    new_lines = []
    current_indent = 0
    
    for line in lines:
        # Track current indentation level
        stripped = line.lstrip()
        if stripped:
            current_indent = len(line) - len(stripped)
        
        # Check for duplicate assignments within same block
        if '=' in line and not line.strip().startswith('#'):
            assignment_match = re.match(r'(\s*)([a-zA-Z_]+)\s*=', line)
            if assignment_match:
                indent = len(assignment_match.group(1))
                var_name = assignment_match.group(2)
                key = f"{indent}_{var_name}"
                
                # If we see the same assignment at the same indent level, skip it
                if key in seen_assignments and 'data_schema' not in line:
                    continue
                seen_assignments.add(key)
        
        # Reset seen assignments when indentation decreases
        if stripped and current_indent < len(line) - len(stripped):
            seen_assignments.clear()
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    return content

def fix_file(file_path):
    """Fix a single file"""
    print(f"Processing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    content = fix_syntax_errors(content)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Fixed syntax errors in {file_path}")
    else:
        print(f"  ⏭️  No syntax errors found in {file_path}")

def fix_specific_files():
    """Fix specific syntax errors in each file"""
    
    # Fix test_full_workflow.py
    file_path = "tests/integration/test_full_workflow.py"
    if os.path.exists(file_path):
        print(f"Fixing {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add missing response = 
        content = re.sub(
            r'(\s+)"/api/v1/data/test-file-123/export",',
            r'\1response = await async_authorized_client.post(\n\1    "/api/v1/data/test-file-123/export",',
            content
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Fixed {file_path}")
    
    # Fix test_data_processing.py
    file_path = "tests/test_api/test_data_processing.py"
    if os.path.exists(file_path):
        print(f"Fixing {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add missing response = 
        content = re.sub(
            r'(\s+)"/api/v1/data/process",',
            r'\1response = await async_authorized_client.post(\n\1    "/api/v1/data/process",',
            content
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Fixed {file_path}")
    
    # Fix test_model_training.py
    file_path = "tests/test_api/test_model_training.py"
    if os.path.exists(file_path):
        print(f"Fixing {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add missing response = and data =
        content = re.sub(
            r'(\s+)"/api/v1/ml/model_123",',
            r'\1response = await async_authorized_client.get(\n\1    "/api/v1/ml/model_123"\n\1)\n\1data = response.json()',
            content
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Fixed {file_path}")
    
    # Fix test_upload.py
    file_path = "tests/test_api/test_upload.py"
    if os.path.exists(file_path):
        print(f"Fixing {file_path}")
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Fix duplicate SchemaField and mismatched bracket
        fixed_lines = []
        skip_next = False
        
        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue
                
            if i == 72 and 'SchemaField(' in line and i > 0 and 'SchemaField(' in lines[i-1]:
                # Skip duplicate SchemaField line
                skip_next = True
                continue
            elif i == 73 and line.strip() == ']):':
                # Fix closing bracket
                fixed_lines.append('            ])\n')
            else:
                fixed_lines.append(line)
        
        with open(file_path, 'w') as f:
            f.writelines(fixed_lines)
        print(f"  ✅ Fixed {file_path}")
    
    # Fix test_user_data.py
    file_path = "tests/test_models/test_user_data.py"
    if os.path.exists(file_path):
        print(f"Fixing {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add missing UserData initialization
        content = re.sub(
            r'def test_user_data_default_timestamps\(\):\s*\n\s*"""Test that UserData automatically sets timestamps."""\s*\n\s*s3_url=',
            'def test_user_data_default_timestamps():\n    """Test that UserData automatically sets timestamps."""\n    user_data = UserData(\n        user_id="test-user",\n        filename="test.csv",\n        original_filename="test.csv",\n        num_rows=10,\n        num_columns=2,\n        s3_url=',
            content
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Fixed {file_path}")

def main():
    """Main function"""
    print("Fixing specific syntax errors in test files...")
    
    # First fix specific errors
    fix_specific_files()
    
    # Then fix general syntax errors
    files_to_fix = [
        "tests/test_api/test_analytics.py",
        "tests/test_api/test_visualization_endpoints.py",
        "tests/test_services/test_visualization_cache.py",
        "tests/test_services/test_ai_summary.py",
    ]
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_file(file_path)

if __name__ == "__main__":
    main()