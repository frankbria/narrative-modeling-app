#!/usr/bin/env python3
"""
Fix test files that use 'client' instead of authorized_client
"""
import re

files_to_fix = {
    "tests/test_api/test_documentation.py": [
        ("response = client.get", "response = authorized_client.get"),
        ("response = client.post", "response = authorized_client.post"),
    ],
    "tests/test_api/test_onboarding.py": [
        ("response = client.get", "response = authorized_client.get"),
        ("response = client.post", "response = authorized_client.post"),
    ],
    "tests/test_api/test_visualization_endpoints.py": [
        ("response = client.get", "response = authorized_client.get"),
        ("async def test_visualization_unauthorized(self, authorized_client", "async def test_visualization_unauthorized(self, client"),
    ],
}

def main():
    for file_path, replacements in files_to_fix.items():
        print(f"Fixing {file_path}")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        # Remove the fixture definition that creates TestClient
        content = re.sub(
            r'@pytest\.fixture\s*\ndef\s+client\(\):\s*\n.*?"Use authorized_client fixture instead".*?\n.*?yield client.*?\n.*?app\.dependency_overrides\.pop\(get_current_user_id, None\)\s*\n',
            '',
            content,
            flags=re.DOTALL
        )
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Fixed {file_path}")

if __name__ == "__main__":
    main()