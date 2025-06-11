"""
Integration tests for complete upload workflows
Tests the full frontend-backend integration scenarios
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
import io
import tempfile
from pathlib import Path
import json


class TestUploadWorkflowIntegration:
    """Test complete upload workflows end-to-end"""

    async def test_small_file_secure_upload_workflow(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test complete workflow for small file secure upload"""
        # Create test CSV file without PII
        csv_data = "product_id,price,category\n1001,19.99,electronics\n1002,29.99,books\n1003,39.99,clothing"
        csv_file = io.BytesIO(csv_data.encode('utf-8'))
        
        # Test the secure upload endpoint
        files = {"file": ("test_products.csv", csv_file, "text/csv")}
        
        response = await mock_async_client.post("/api/upload/secure", files=files)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches frontend expectations
        assert data["status"] == "success"
        assert "file_id" in data
        assert "filename" in data
        assert data["filename"] == "test_products.csv"
        assert "pii_report" in data
        assert data["pii_report"]["has_pii"] is False
        assert "preview" in data
        assert len(data["preview"]) > 0

    async def test_pii_detection_workflow(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test PII detection workflow matching frontend expectations"""
        # Create test CSV file with PII
        csv_data = "name,email,phone,salary\nJohn Doe,john@example.com,555-123-4567,50000\nJane Smith,jane@test.com,555-987-6543,60000"
        csv_file = io.BytesIO(csv_data.encode('utf-8'))
        
        files = {"file": ("employee_data.csv", csv_file, "text/csv")}
        
        response = await mock_async_client.post("/api/upload/secure", files=files)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect PII and provide proper response structure
        assert "pii_report" in data
        pii_report = data["pii_report"]
        
        # Verify PII report structure matches frontend interfaces
        assert "has_pii" in pii_report
        assert "detections" in pii_report
        assert "risk_level" in pii_report
        assert "total_detections" in pii_report
        assert "affected_columns" in pii_report
        
        # Check if high-risk PII triggers confirmation requirement
        if pii_report["risk_level"] == "high":
            assert data.get("requires_confirmation", False)

    async def test_chunked_upload_init_workflow(self, mock_async_client: AsyncClient, mock_upload_handler):
        """Test chunked upload initialization workflow"""
        # Test initialization for large file
        init_params = {
            "filename": "large_dataset.csv",
            "file_size": 100 * 1024 * 1024,  # 100MB
            "file_hash": "abc123def456"
        }
        
        response = await mock_async_client.post(
            "/api/upload/chunked/init",
            params=init_params
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches useChunkedUpload hook expectations
        assert "session_id" in data
        assert "chunk_size" in data
        assert "total_chunks" in data
        assert "expires_at" in data
        
        return data["session_id"]

    async def test_chunked_upload_chunk_workflow(self, mock_async_client: AsyncClient, mock_upload_handler):
        """Test chunked upload chunk workflow"""
        # Use mocked session ID directly
        session_id = "test_session_123"
        
        # Create test chunk data
        chunk_data = b"product_id,name,price\n1001,Widget A,19.99\n1002,Widget B,29.99"
        files = {"file": ("chunk_0", io.BytesIO(chunk_data), "application/octet-stream")}
        
        response = await mock_async_client.post(
            f"/api/upload/chunked/{session_id}/chunk/0",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches progress tracking expectations
        assert "chunk_number" in data
        assert "status" in data
        assert "progress" in data
        assert data["chunk_number"] == 0
        assert data["status"] in ["uploaded", "already_uploaded"]

    async def test_chunked_upload_resume_workflow(self, mock_async_client: AsyncClient, mock_upload_handler):
        """Test chunked upload resume workflow"""
        # Initialize and upload a chunk first
        session_id = await self.test_chunked_upload_init_workflow(mock_async_client, mock_upload_handler)
        await self.test_chunked_upload_chunk_workflow(mock_async_client, mock_upload_handler)
        
        # Test resume functionality
        response = await mock_async_client.get(f"/api/upload/chunked/{session_id}/resume")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches resume functionality expectations
        assert "session_id" in data
        assert "uploaded_chunks" in data
        assert "missing_chunks" in data
        assert "progress" in data
        assert "total_chunks" in data
        assert data["session_id"] == session_id

    async def test_health_endpoints_workflow(self, mock_async_client: AsyncClient):
        """Test health endpoints for frontend monitoring integration"""
        # Test health status
        response = await mock_async_client.get("/api/health/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        
        # Test health metrics
        response = await mock_async_client.get("/api/health/metrics")
        assert response.status_code == 200
        
        metrics = response.json()
        # Verify metrics structure matches frontend dashboard expectations
        expected_metrics = ["memory_usage", "active_counters", "total_requests"]
        for metric in expected_metrics:
            assert metric in metrics or any(metric in str(v) for v in metrics.values())

    async def test_error_handling_workflow(self, mock_async_client: AsyncClient):
        """Test error handling scenarios match frontend expectations"""
        # Test invalid file type
        invalid_file = io.BytesIO(b"This is not a valid CSV file content")
        files = {"file": ("test.txt", invalid_file, "text/plain")}
        
        response = await mock_async_client.post("/api/upload/secure", files=files)
        
        # Should return 400 error with proper error structure
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data  # FastAPI standard error format

    async def test_authentication_workflow(self, mock_async_client: AsyncClient):
        """Test authentication requirements match frontend token handling"""
        # Test upload without authentication (should use mock auth)
        csv_data = "test,data\n1,2"
        csv_file = io.BytesIO(csv_data.encode('utf-8'))
        files = {"file": ("test.csv", csv_file, "text/csv")}
        
        # This should work with mock authentication from conftest.py
        response = await mock_async_client.post("/api/upload/secure", files=files)
        assert response.status_code == 200

    async def test_file_size_limits_workflow(self, mock_async_client: AsyncClient, mock_upload_handler):
        """Test file size limit enforcement workflow"""
        # Test file too large for chunked upload
        large_payload = {
            "filename": "massive_file.csv",
            "file_size": 200 * 1024 * 1024 * 1024,  # 200GB - exceeds limit
            "file_hash": "test_hash"
        }
        
        response = await mock_async_client.post(
            "/api/upload/chunked/init",
            params=large_payload
        )
        
        # Should reject file that's too large
        assert response.status_code == 413

    async def test_concurrent_upload_workflow(self, mock_async_client: AsyncClient, mock_upload_handler):
        """Test concurrent upload handling workflow"""
        # Test multiple upload initializations
        tasks = []
        for i in range(3):
            payload = {
                "filename": f"file_{i}.csv",
                "file_size": 1024,
                "file_hash": f"hash_{i}"
            }
            
            response = await mock_async_client.post(
                "/api/upload/chunked/init",
                params=payload
            )
            assert response.status_code == 200
            tasks.append(response.json()["session_id"])
        
        # All sessions should be unique
        assert len(set(tasks)) == 3

    async def test_complete_upload_workflow_integration(self, mock_async_client: AsyncClient, mock_upload_handler):
        """Test complete end-to-end upload workflow"""
        # 1. Initialize chunked upload
        session_id = await self.test_chunked_upload_init_workflow(mock_async_client, mock_upload_handler)
        
        # 2. Upload chunks
        await self.test_chunked_upload_chunk_workflow(mock_async_client, mock_upload_handler)
        
        # 3. Complete upload
        response = await mock_async_client.post(f"/api/upload/chunked/{session_id}/complete")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify complete upload response matches frontend expectations
        assert data["status"] == "success"
        assert "file_id" in data
        assert "filename" in data
        assert "pii_report" in data
        
        # Should have processed the file and detected any PII
        pii_report = data["pii_report"]
        assert "has_pii" in pii_report
        assert "risk_level" in pii_report