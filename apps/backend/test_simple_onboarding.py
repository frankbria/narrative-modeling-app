"""
Simple test to verify onboarding routes work
"""
from fastapi.testclient import TestClient
from app.main import app

# Override auth dependency for testing
def fake_get_current_user_id():
    return "test_user_123"

from app.api.deps import get_current_user_id
app.dependency_overrides[get_current_user_id] = fake_get_current_user_id

client = TestClient(app)

def test_routes_exist():
    """Test that onboarding routes are registered"""
    
    # Test a simple endpoint
    response = client.get("/api/v1/onboarding/sample-datasets")
    print(f"Sample datasets response: {response.status_code}")
    print(f"Response content: {response.text[:200]}")
    
    # Test status endpoint
    response = client.get("/api/v1/onboarding/status") 
    print(f"Status response: {response.status_code}")
    print(f"Response content: {response.text[:200]}")

if __name__ == "__main__":
    test_routes_exist()