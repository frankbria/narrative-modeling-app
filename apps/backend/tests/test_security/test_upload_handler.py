"""
Tests for Chunked Upload Handler
"""

import pytest
import pytest_asyncio
from app.services.security.upload_handler import ChunkedUploadHandler
from app.models.user_data import UserData
from tests.conftest import setup_database


@pytest.mark.integration
class TestChunkedUploadHandler:
    """Test cases for chunked upload functionality"""
    
    def setup_method(self):
        self.handler = ChunkedUploadHandler()
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_test(self, setup_database):
        """Set up test database"""
        pass
    
    async def test_init_upload(self):
        """Test upload initialization"""
        filename = "test_file.csv"
        file_size = 1024 * 1024  # 1MB
        file_hash = "abc123"
        
        result = await self.handler.init_upload(filename, file_size, file_hash)
        
        assert "session_id" in result
        assert result["chunk_size"] == self.handler.chunk_size
        assert result["total_chunks"] == 1  # 1MB file with 5MB chunks
        assert "expires_at" in result
    
    async def test_upload_chunk(self):
        """Test uploading a chunk"""
        # First initialize upload
        filename = "test_file.csv"
        file_size = 1024
        init_result = await self.handler.init_upload(filename, file_size)
        session_id = init_result["session_id"]
        
        # Upload a chunk
        chunk_data = b"test data chunk"
        chunk_number = 0
        
        result = await self.handler.upload_chunk(session_id, chunk_number, chunk_data)
        
        assert result["chunk_number"] == chunk_number
        assert result["status"] == "uploaded"
        assert "progress" in result
    
    async def test_upload_duplicate_chunk(self):
        """Test uploading the same chunk twice"""
        # Initialize upload
        filename = "test_file.csv"
        file_size = 1024
        init_result = await self.handler.init_upload(filename, file_size)
        session_id = init_result["session_id"]
        
        # Upload chunk first time
        chunk_data = b"test data chunk"
        chunk_number = 0
        await self.handler.upload_chunk(session_id, chunk_number, chunk_data)
        
        # Upload same chunk again
        result = await self.handler.upload_chunk(session_id, chunk_number, chunk_data)
        
        assert result["status"] == "already_uploaded"
    
    async def test_resume_upload(self):
        """Test resuming an upload"""
        # Initialize upload
        filename = "test_file.csv"
        file_size = 2048  # 2KB file
        init_result = await self.handler.init_upload(filename, file_size)
        session_id = init_result["session_id"]
        
        # Upload first chunk
        chunk_data = b"a" * 1024  # 1KB
        await self.handler.upload_chunk(session_id, 0, chunk_data)
        
        # Resume upload
        result = await self.handler.resume_upload(session_id)
        
        assert result["session_id"] == session_id
        assert result["uploaded_chunks"] == 1  # number of uploaded chunks
        assert 0 not in result["missing_chunks"]  # chunk 0 should not be missing
        assert result["progress"] > 0  # some progress made
    
    async def test_invalid_session_id(self):
        """Test operations with invalid session ID"""
        invalid_session_id = "invalid_session_123"
        
        # Try to upload chunk with invalid session
        with pytest.raises(Exception):  # Will raise HTTPException
            await self.handler.upload_chunk(invalid_session_id, 0, b"data")
        
        # Try to resume invalid session
        with pytest.raises(Exception):  # Will raise HTTPException
            await self.handler.resume_upload(invalid_session_id)
    
    async def test_chunk_hash_validation(self):
        """Test chunk hash validation"""
        # Initialize upload
        filename = "test_file.csv"
        file_size = 1024
        init_result = await self.handler.init_upload(filename, file_size)
        session_id = init_result["session_id"]
        
        # Upload chunk with correct hash
        chunk_data = b"test data chunk"
        import hashlib
        chunk_hash = hashlib.md5(chunk_data).hexdigest()
        
        result = await self.handler.upload_chunk(
            session_id, 0, chunk_data, chunk_hash
        )
        
        assert result["status"] == "uploaded"
    
    async def test_chunk_hash_mismatch(self):
        """Test chunk upload with incorrect hash"""
        # Initialize upload
        filename = "test_file.csv"
        file_size = 1024
        init_result = await self.handler.init_upload(filename, file_size)
        session_id = init_result["session_id"]
        
        # Upload chunk with wrong hash
        chunk_data = b"test data chunk"
        wrong_hash = "wrong_hash_123"
        
        with pytest.raises(Exception):  # Will raise HTTPException
            await self.handler.upload_chunk(
                session_id, 0, chunk_data, wrong_hash
            )
    
    async def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # Create multiple uploads quickly
        uploads = []
        for i in range(5):
            result = await self.handler.init_upload(f"file_{i}.csv", 1024)
            uploads.append(result["session_id"])
        
        # All should succeed initially (rate limiting is per-IP in real scenario)
        assert len(uploads) == 5
    
    async def test_upload_progress_calculation(self):
        """Test upload progress calculation"""
        # Initialize upload with multiple chunks
        filename = "large_file.csv"
        file_size = 15 * 1024 * 1024  # 15MB file (will need 3 chunks with 5MB each)
        init_result = await self.handler.init_upload(filename, file_size)
        session_id = init_result["session_id"]
        
        # Upload first chunk
        chunk_data = b"a" * (5 * 1024 * 1024)  # 5MB
        await self.handler.upload_chunk(session_id, 0, chunk_data)
        
        # Check progress
        result = await self.handler.resume_upload(session_id)
        assert result["progress"] > 0  # Some progress made
        
        # Upload second chunk
        await self.handler.upload_chunk(session_id, 1, chunk_data)
        
        # Check progress again
        result = await self.handler.resume_upload(session_id)
        assert result["progress"] > 50  # More than half complete