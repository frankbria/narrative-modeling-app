#!/usr/bin/env python3
"""
Script to analyze and fix test issues in the backend test suite
"""
import os
import re
from pathlib import Path

def find_userdata_creation_patterns(test_dir="tests"):
    """Find all files that create UserData objects with old schema"""
    issues = []
    test_path = Path(test_dir)
    
    patterns = [
        r'UserData\s*\(',  # Direct UserData creation
        r'file_path\s*=',  # Old field name
        r'file_size\s*=',  # Old field name
        r'file_type\s*=',  # Old field name
        r'upload_date\s*=',  # Old field name
        r'is_processed\s*=',  # Old field name
    ]
    
    for py_file in test_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
            
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            for pattern in patterns:
                if re.search(pattern, line):
                    issues.append({
                        'file': str(py_file),
                        'line': i,
                        'content': line.strip(),
                        'pattern': pattern
                    })
    
    return issues

def analyze_auth_issues(test_dir="tests"):
    """Find tests that might still have auth issues"""
    issues = []
    test_path = Path(test_dir)
    
    patterns = [
        r'clerk_auth',  # Old auth module
        r'TestClient\s*\(',  # Direct TestClient usage without auth
        r'authorized_client',  # Using authorized_client fixture
    ]
    
    for py_file in test_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
            
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            for pattern in patterns:
                if re.search(pattern, line):
                    issues.append({
                        'file': str(py_file),
                        'line': i,
                        'content': line.strip(),
                        'pattern': pattern
                    })
    
    return issues

def main():
    print("Analyzing test issues...")
    print("=" * 80)
    
    # Find UserData schema issues
    print("\n### UserData Schema Issues ###")
    userdata_issues = find_userdata_creation_patterns()
    
    # Group by file
    files_with_issues = {}
    for issue in userdata_issues:
        if issue['file'] not in files_with_issues:
            files_with_issues[issue['file']] = []
        files_with_issues[issue['file']].append(issue)
    
    print(f"\nFound {len(files_with_issues)} files with UserData schema issues:")
    for file, issues in files_with_issues.items():
        print(f"\n{file}:")
        unique_patterns = set(issue['pattern'] for issue in issues)
        for pattern in unique_patterns:
            count = sum(1 for issue in issues if issue['pattern'] == pattern)
            print(f"  - {pattern.strip()}: {count} occurrences")
    
    # Find auth issues
    print("\n\n### Authentication Issues ###")
    auth_issues = analyze_auth_issues()
    
    # Group by file
    auth_files = {}
    for issue in auth_issues:
        if issue['file'] not in auth_files:
            auth_files[issue['file']] = []
        auth_files[issue['file']].append(issue)
    
    print(f"\nFound {len(auth_files)} files with potential auth issues:")
    for file, issues in auth_files.items():
        print(f"\n{file}:")
        unique_patterns = set(issue['pattern'] for issue in issues)
        for pattern in unique_patterns:
            count = sum(1 for issue in issues if issue['pattern'] == pattern)
            print(f"  - {pattern.strip()}: {count} occurrences")
    
    # Summary
    print("\n\n### Summary ###")
    print(f"Total files with UserData issues: {len(files_with_issues)}")
    print(f"Total files with auth issues: {len(auth_files)}")
    print(f"\nMost common issue patterns:")
    
    all_patterns = {}
    for issue in userdata_issues + auth_issues:
        pattern = issue['pattern']
        all_patterns[pattern] = all_patterns.get(pattern, 0) + 1
    
    for pattern, count in sorted(all_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {pattern.strip()}: {count} occurrences")

if __name__ == "__main__":
    main()