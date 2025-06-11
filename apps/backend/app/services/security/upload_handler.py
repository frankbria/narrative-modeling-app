"""
Resilient Upload Handler
Handles network interruptions, large files, and security checks
"""

import os
import hashlib
import json
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime, timedelta
import aiofiles
from fastapi import UploadFile, HTTPException
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ChunkedUploadHandler:
    """Handles resumable chunked uploads with integrity checks"""
    
    def __init__(self, 
                 temp_dir: str = "/tmp/uploads",
                 chunk_size: int = 5 * 1024 * 1024,  # 5MB chunks
                 max_file_size: int = 100 * 1024 * 1024 * 1024,  # 100GB
                 session_timeout: int = 24):  # hours
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size
        self.session_timeout = session_timeout
        self.sessions = {}  # In production, use Redis
    
    async def init_upload(self, 
                          filename: str, 
                          file_size: int,
                          file_hash: Optional[str] = None) -> Dict[str, Any]:
        """Initialize a new upload session"""
        
        # Validate file size
        if file_size > self.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {self.max_file_size / (1024**3):.1f}GB"
            )
        
        # Generate session ID
        session_id = self._generate_session_id(filename, file_size)
        
        # Calculate chunks
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        # Create temp file path
        temp_path = self.temp_dir / f"{session_id}.tmp"
        
        # Initialize session
        session = {
            "id": session_id,
            "filename": filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "total_chunks": total_chunks,
            "uploaded_chunks": [],
            "temp_path": str(temp_path),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=self.session_timeout)).isoformat(),
            "status": "initialized"
        }
        
        # Save session (in production, use Redis)
        self.sessions[session_id] = session
        self._save_session_metadata(session_id, session)
        
        return {
            "session_id": session_id,
            "chunk_size": self.chunk_size,
            "total_chunks": total_chunks,
            "expires_at": session["expires_at"]
        }
    
    async def upload_chunk(self,
                          session_id: str,
                          chunk_number: int,
                          chunk_data: bytes,
                          chunk_hash: Optional[str] = None) -> Dict[str, Any]:
        """Upload a single chunk"""
        
        # Get session
        session = self._get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        # Validate chunk number
        if chunk_number >= session["total_chunks"]:
            raise HTTPException(status_code=400, detail="Invalid chunk number")
        
        # Check if chunk already uploaded
        if chunk_number in session["uploaded_chunks"]:
            return {
                "chunk_number": chunk_number,
                "status": "already_uploaded",
                "progress": self._calculate_progress(session)
            }
        
        # Verify chunk hash if provided
        if chunk_hash:
            actual_hash = hashlib.md5(chunk_data).hexdigest()
            if actual_hash != chunk_hash:
                raise HTTPException(
                    status_code=400,
                    detail=f"Chunk hash mismatch. Expected: {chunk_hash}, Got: {actual_hash}"
                )
        
        # Write chunk to temp file
        temp_path = Path(session["temp_path"])
        offset = chunk_number * self.chunk_size
        
        async with aiofiles.open(temp_path, 'r+b' if temp_path.exists() else 'wb') as f:
            await f.seek(offset)
            await f.write(chunk_data)
        
        # Update session
        session["uploaded_chunks"].append(chunk_number)
        session["uploaded_chunks"].sort()
        session["last_activity"] = datetime.utcnow().isoformat()
        
        # Check if upload is complete
        if len(session["uploaded_chunks"]) == session["total_chunks"]:
            session["status"] = "complete"
            
            # Verify complete file if hash provided
            if session.get("file_hash"):
                file_valid = await self._verify_file_integrity(
                    temp_path, 
                    session["file_hash"]
                )
                if not file_valid:
                    session["status"] = "failed"
                    raise HTTPException(
                        status_code=400,
                        detail="File integrity check failed"
                    )
        
        # Save session state
        self.sessions[session_id] = session
        self._save_session_metadata(session_id, session)
        
        return {
            "chunk_number": chunk_number,
            "status": "uploaded",
            "progress": self._calculate_progress(session),
            "complete": session["status"] == "complete"
        }
    
    async def resume_upload(self, session_id: str) -> Dict[str, Any]:
        """Get resume information for interrupted upload"""
        
        session = self._get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        # Check expiration
        if datetime.fromisoformat(session["expires_at"]) < datetime.utcnow():
            raise HTTPException(status_code=410, detail="Upload session expired")
        
        # Find missing chunks
        all_chunks = list(range(session["total_chunks"]))
        missing_chunks = [c for c in all_chunks if c not in session["uploaded_chunks"]]
        
        return {
            "session_id": session_id,
            "filename": session["filename"],
            "file_size": session["file_size"],
            "chunk_size": self.chunk_size,
            "total_chunks": session["total_chunks"],
            "uploaded_chunks": len(session["uploaded_chunks"]),
            "missing_chunks": missing_chunks,
            "progress": self._calculate_progress(session),
            "expires_at": session["expires_at"]
        }
    
    async def complete_upload(self, session_id: str) -> Path:
        """Finalize upload and return file path"""
        
        session = self._get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        if session["status"] != "complete":
            raise HTTPException(
                status_code=400,
                detail=f"Upload not complete. Progress: {self._calculate_progress(session)}%"
            )
        
        return Path(session["temp_path"])
    
    def cleanup_expired_sessions(self):
        """Clean up expired upload sessions"""
        now = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if datetime.fromisoformat(session["expires_at"]) < now:
                expired_sessions.append(session_id)
                
                # Delete temp file
                temp_path = Path(session["temp_path"])
                if temp_path.exists():
                    temp_path.unlink()
        
        # Remove expired sessions
        for session_id in expired_sessions:
            del self.sessions[session_id]
            metadata_path = self.temp_dir / f"{session_id}.json"
            if metadata_path.exists():
                metadata_path.unlink()
        
        return len(expired_sessions)
    
    def _generate_session_id(self, filename: str, file_size: int) -> str:
        """Generate unique session ID"""
        data = f"{filename}:{file_size}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from memory or disk"""
        # Check memory first
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try loading from disk
        metadata_path = self.temp_dir / f"{session_id}.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                session = json.load(f)
                self.sessions[session_id] = session
                return session
        
        return None
    
    def _save_session_metadata(self, session_id: str, session: Dict[str, Any]):
        """Save session metadata to disk for recovery"""
        metadata_path = self.temp_dir / f"{session_id}.json"
        with open(metadata_path, 'w') as f:
            json.dump(session, f)
    
    def _calculate_progress(self, session: Dict[str, Any]) -> float:
        """Calculate upload progress percentage"""
        return round(len(session["uploaded_chunks"]) / session["total_chunks"] * 100, 2)
    
    async def _verify_file_integrity(self, file_path: Path, expected_hash: str) -> bool:
        """Verify file integrity using hash"""
        hash_algo = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_algo.update(chunk)
        
        actual_hash = hash_algo.hexdigest()
        return actual_hash == expected_hash


class RateLimiter:
    """Simple rate limiter for upload protection"""
    
    def __init__(self,
                 max_requests_per_minute: int = 60,
                 max_concurrent_uploads: int = 10):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent_uploads = max_concurrent_uploads
        self.request_times = {}  # user_id -> [timestamps]
        self.active_uploads = {}  # user_id -> count
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old entries
        if user_id in self.request_times:
            self.request_times[user_id] = [
                t for t in self.request_times[user_id] 
                if t > minute_ago
            ]
        
        # Check rate
        request_count = len(self.request_times.get(user_id, []))
        return request_count < self.max_requests_per_minute
    
    def check_concurrent_limit(self, user_id: str) -> bool:
        """Check if user can start another upload"""
        active_count = self.active_uploads.get(user_id, 0)
        return active_count < self.max_concurrent_uploads
    
    def record_request(self, user_id: str):
        """Record a new request"""
        if user_id not in self.request_times:
            self.request_times[user_id] = []
        self.request_times[user_id].append(datetime.utcnow())
    
    def start_upload(self, user_id: str):
        """Record upload start"""
        if user_id not in self.active_uploads:
            self.active_uploads[user_id] = 0
        self.active_uploads[user_id] += 1
    
    def end_upload(self, user_id: str):
        """Record upload end"""
        if user_id in self.active_uploads:
            self.active_uploads[user_id] = max(0, self.active_uploads[user_id] - 1)