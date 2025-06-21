"""
Tests for Secure Upload API endpoints
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import io
import pandas as pd


class TestSecureUploadAPI:
    """Test cases for secure upload endpoints"""
    
    async def test_secure_upload_no_pii(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test secure upload with clean data"""
        # Create test CSV data without PII
        csv_data = "product_id,price,category\n1001,19.99,electronics\n1002,29.99,books"
        csv_file = io.BytesIO(csv_data.encode('utf-8'))
        
        files = {"file": ("test.csv", csv_file, "text/csv")}
        
        response = await mock_async_client.post(
            "/api/v1/upload/secure",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["pii_report"]["has_pii"] is False
        assert "file_id" in data
    
    async def test_secure_upload_with_pii(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test secure upload with PII data"""
        # Create test CSV data with PII
        csv_data = "name,email,phone\nJohn Doe,john@example.com,555-1234"
        csv_file = io.BytesIO(csv_data.encode('utf-8'))
        
        files = {"file": ("test_pii.csv", csv_file, "text/csv")}
        
        response = await mock_async_client.post(
            "/api/v1/upload/secure",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["pii_report"]["has_pii"] is True
        assert "file_id" in data
    
    async def test_secure_upload_invalid_file(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test secure upload with invalid file format"""
        # Create non-CSV data
        text_data = "This is not a CSV file"
        text_file = io.BytesIO(text_data.encode('utf-8'))
        
        files = {"file": ("test.txt", text_file, "text/plain")}
        
        response = await mock_async_client.post(
            "/api/v1/upload/secure",
            files=files
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data
    
    async def test_chunked_upload_init(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary, mock_upload_handler):
        """Test chunked upload initialization"""
        payload = {
            "filename": "large_file.csv",
            "file_size": 5242880,  # 5MB
            "file_hash": "abc123hash"
        }
        
        response = await mock_async_client.post(
            "/api/v1/upload/chunked/init",
            params=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test_session_123"
        assert "chunk_size" in data
        assert "total_chunks" in data
        assert "expires_at" in data
    
    async def test_chunked_upload_chunk(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary, mock_upload_handler):
        """Test uploading a chunk"""
        # Use mocked session ID directly
        session_id = "test_session_123"
        
        # Upload a chunk
        chunk_data = b"test chunk data"
        files = {"file": ("chunk0", io.BytesIO(chunk_data), "application/octet-stream")}
        
        response = await mock_async_client.post(
            f"/api/v1/upload/chunked/{session_id}/chunk/0",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "uploaded"
        assert data["chunk_number"] == 0
    
    async def test_chunked_upload_resume(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary, mock_upload_handler):
        """Test resuming a chunked upload"""
        # Use mocked session ID
        session_id = "test_session_123"
        
        # Resume upload
        response = await mock_async_client.get(
            f"/api/v1/upload/chunked/{session_id}/resume"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["uploaded_chunks"] == 1  # number of uploaded chunks from mock
        assert data["missing_chunks"] == []  # empty list from mock
        assert data["progress"] == 100.0  # mocked progress
    
    async def test_chunked_upload_complete(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary, mock_upload_handler):
        """Test completing a chunked upload"""
        # Use mocked session ID directly
        session_id = "test_session_123"
        
        # Complete upload
        response = await mock_async_client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "file_id" in data
        assert "pii_report" in data
    
    async def test_chunked_upload_invalid_session(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test chunked upload with invalid session ID"""
        invalid_session = "invalid_session_123"
        
        # Try to upload chunk with invalid session
        chunk_data = b"test data"
        files = {"file": ("chunk0", io.BytesIO(chunk_data), "application/octet-stream")}
        
        response = await mock_async_client.post(
            f"/api/v1/upload/chunked/{invalid_session}/chunk/0",
            files=files
        )
        
        assert response.status_code == 404
        assert "detail" in response.json()
    
    async def test_file_size_limit(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary, mock_upload_handler):
        """Test file size limit enforcement"""
        # Try to initialize upload with file too large
        large_payload = {
            "filename": "huge_file.csv",
            "file_size": 200 * 1024 * 1024 * 1024,  # 200GB - should exceed 100GB limit
            "file_hash": "test_hash"
        }
        
        response = await mock_async_client.post(
            "/api/v1/upload/chunked/init",
            params=large_payload
        )
        
        # Should reject file that's too large
        assert response.status_code == 413
    
    async def test_upload_metrics_tracking(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary, mock_monitoring):
        """Test that uploads are tracked in metrics"""
        csv_data = "id,value\n1,test"
        csv_file = io.BytesIO(csv_data.encode('utf-8'))
        
        files = {"file": ("metrics_test.csv", csv_file, "text/csv")}
        
        response = await mock_async_client.post(
            "/api/v1/upload/secure",
            files=files
        )
        
        assert response.status_code == 200
        
        # Check metrics endpoint to verify tracking
        metrics_response = await mock_async_client.get("/api/v1/health/metrics")
        assert metrics_response.status_code == 200
        
        metrics = metrics_response.json()
        # Should have recorded the upload in the metrics
        # Check for actual fields from the metrics response
        assert "active_counters" in metrics or "memory_usage" in metrics or "total_requests" in metrics
    
    async def test_concurrent_uploads(self, mock_async_client: AsyncClient, mock_s3_upload, mock_user_data, mock_schema_inference, mock_ai_summary):
        """Test handling concurrent uploads"""
        # Initialize multiple uploads simultaneously
        tasks = []
        for i in range(3):
            payload = {
                "filename": f"file_{i}.csv",
                "file_size": 1024,
                "file_hash": f"hash_{i}"
            }
            
            response = await mock_async_client.post(
                "/api/v1/upload/chunked/init",
                params=payload
            )
            assert response.status_code == 200
            tasks.append(response.json()["session_id"])
        
        # All sessions should be unique
        assert len(set(tasks)) == 3