#!/usr/bin/env python3
"""
Script to fix UserData field names in tests
"""
import os
import re
from pathlib import Path

# Mapping of old field names to new field names
FIELD_MAPPINGS = {
    'file_path': 's3_url',
    'file_size': None,  # This is now computed/not stored
    'file_type': None,  # This is now computed/not stored
    'upload_date': 'created_at',
    'is_processed': None,  # This field might not exist anymore
    'schema': 'data_schema',  # Assuming this mapping
}

def fix_file(file_path):
    """Fix UserData field names in a single file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace field names in assignments and comparisons
    for old_field, new_field in FIELD_MAPPINGS.items():
        if new_field:
            # Replace in assignments like file_path="..." or file_path:
            content = re.sub(
                rf'\b{old_field}\s*[:=]',
                f'{new_field}:',
                content
            )
            # Replace in attribute access like .file_path
            content = re.sub(
                rf'\.{old_field}\b',
                f'.{new_field}',
                content
            )
    
    # Special handling for removed fields
    # Comment out lines that only set removed fields
    for old_field in ['file_size', 'file_type', 'is_processed']:
        # Comment out simple assignments
        content = re.sub(
            rf'^(\s*){old_field}\s*=\s*[^,\n]+,?\s*$',
            r'\1# \g<0>  # TODO: Field removed from UserData model',
            content,
            flags=re.MULTILINE
        )
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix UserData fields in all test files"""
    test_dir = Path("tests")
    fixed_files = []
    
    for py_file in test_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        if fix_file(py_file):
            fixed_files.append(py_file)
    
    print(f"Fixed {len(fixed_files)} files:")
    for f in fixed_files:
        print(f"  - {f}")
    
    print("\nNote: You'll need to manually review and fix:")
    print("  - UserData() constructor calls with old parameters")
    print("  - References to removed fields (file_size, file_type, is_processed)")
    print("  - Mock objects that simulate UserData")

if __name__ == "__main__":
    main()