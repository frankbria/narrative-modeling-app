#!/usr/bin/env python3
"""
Test script to verify transformation API endpoints are working
"""
import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set environment variables for testing
os.environ["SKIP_AUTH"] = "true"
os.environ["MONGODB_URI"] = "mongodb://localhost:27017"
os.environ["MONGODB_DB"] = "test_db"

API_BASE_URL = "http://localhost:8000/api/v1"

async def test_transformation_endpoints():
    """Test that transformation endpoints are accessible"""
    async with httpx.AsyncClient() as client:
        try:
            # Test the OpenAPI documentation endpoint to see if transformations are listed
            response = await client.get(f"{API_BASE_URL}/../openapi.json")
            
            if response.status_code == 200:
                openapi_data = response.json()
                
                # Check if transformation endpoints are present
                transformation_endpoints = [
                    path for path in openapi_data.get("paths", {}).keys()
                    if "transformations" in path
                ]
                
                if transformation_endpoints:
                    print("✅ Transformation endpoints found in OpenAPI spec:")
                    for endpoint in transformation_endpoints:
                        print(f"   - {endpoint}")
                    return True
                else:
                    print("❌ No transformation endpoints found in OpenAPI spec")
                    return False
            else:
                print(f"❌ Failed to get OpenAPI spec: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing endpoints: {e}")
            return False

async def main():
    """Main test function"""
    print("Testing Transformation API Integration...")
    print("=" * 50)
    
    # Test endpoint accessibility
    success = await test_transformation_endpoints()
    
    if success:
        print("\n🎉 Transformation API integration test PASSED!")
        print("\nNext steps:")
        print("1. Start the backend server: uvicorn app.main:app --reload")
        print("2. Start the frontend: npm run dev") 
        print("3. Navigate to the transform page with a dataset ID")
        print("4. Test the transformation pipeline functionality")
    else:
        print("\n❌ Transformation API integration test FAILED!")
        print("\nCheck the transformation routes setup in main.py")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)