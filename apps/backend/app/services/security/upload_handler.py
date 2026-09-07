"""
Resilient Upload Handler
Handles network interruptions, large files, and security checks
"""

import hashlib
import json
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import HTTPException

from app.utils.upload_limits import MAX_UPLOAD_BYTES

logger = logging.getLogger(__name__)

# Session ids are secrets.token_urlsafe output, and they are also spliced into
# filenames under temp_dir. Anything outside this alphabet is a caller trying to
# escape the directory (issue #454).
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class ChunkedUploadHandler:
    """Handles resumable chunked uploads with integrity checks"""
    
    def __init__(self, 
                 temp_dir: str = "/tmp/uploads",
                 chunk_size: int = 5 * 1024 * 1024,  # 5MB chunks
                 # Same 100 MB cap as read_upload_capped / BodySizeLimitMiddleware
                 # (issue #270). Bounds chunked disk usage at init: without this the
                 # old 100 GB default let ~100 GB of ≤100 MB chunks land on disk
                 # before the completion size-check fired (disk-DoS).
                 max_file_size: int = MAX_UPLOAD_BYTES,
                 session_timeout: int = 24):  # hours
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size
        self.session_timeout = session_timeout
        self.sessions: dict[str, dict[str, Any]] = {}  # In production, use Redis
    
    async def init_upload(self,
                          user_id: str,
                          filename: str,
                          file_size: int,
                          file_hash: str | None = None) -> dict[str, Any]:
        """Initialize a new upload session owned by ``user_id``."""
        
        # Validate file size
        if file_size <= 0:
            raise HTTPException(
                status_code=400,
                detail="file_size must be greater than zero",
            )

        if file_size > self.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {self.max_file_size // (1024 * 1024)} MB"
            )
        
        # Generate session ID
        session_id = self._generate_session_id()
        
        # Calculate chunks
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        # Create temp file path
        temp_path = self.temp_dir / f"{session_id}.tmp"
        
        # Initialize session
        session = {
            "id": session_id,
            "user_id": user_id,
            "filename": filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "total_chunks": total_chunks,
            "uploaded_chunks": [],
            "temp_path": str(temp_path),
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(hours=self.session_timeout)).isoformat(),
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
                          user_id: str,
                          chunk_number: int,
                          chunk_data: bytes,
                          chunk_hash: str | None = None) -> dict[str, Any]:
        """Upload a single chunk into ``user_id``'s session."""

        # Get session
        session = self.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        # Validate chunk number
        if chunk_number >= session["total_chunks"]:
            raise HTTPException(status_code=400, detail="Invalid chunk number")

        # Bound the payload by the declared geometry. Only read_upload_capped's
        # 100 MB applied before, so a session declaring a small file could still
        # put ~2x MAX_UPLOAD_BYTES on disk (last-slot offset plus one oversized
        # chunk) — which is the disk-DoS the init-time cap (issue #270) is
        # supposed to prevent.
        if len(chunk_data) > self.chunk_size:
            raise HTTPException(
                status_code=413,
                detail=f"Chunk exceeds the declared chunk size of {self.chunk_size} bytes",
            )
        
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
        session["last_activity"] = datetime.now(UTC).isoformat()
        
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
    
    async def resume_upload(self, session_id: str, user_id: str) -> dict[str, Any]:
        """Get resume information for interrupted upload"""

        session = self.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        # Check expiration
        if datetime.fromisoformat(session["expires_at"]) < datetime.now(UTC):
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
    
    def claim_upload(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """Take a fully-uploaded session for finalisation, or return None.

        The session is removed in the same synchronous step it is read, so a
        second concurrent complete — a double-click, or a client retrying after
        a timeout — finds nothing rather than racing to a second S3 object, a
        second UserData row and a second charged quota unit. Everything after
        the claim runs on the returned copy.
        """
        session = self.get_session(session_id, user_id)
        if session is None:
            return None

        if session["status"] != "complete":
            raise HTTPException(
                status_code=400,
                detail=f"Upload not complete. Progress: {self._calculate_progress(session)}%"
            )

        self.sessions.pop(session_id, None)
        (self.temp_dir / f"{session_id}.json").unlink(missing_ok=True)
        return session
    
    def abort_upload(self, session_id: str, user_id: str) -> bool:
        """Discard ``user_id``'s session and its partial file.

        Without this a cancelled upload leaves its .tmp on disk until the 24h
        expiry sweep.
        """
        session = self.get_session(session_id, user_id)
        if session is None:
            return False

        Path(session["temp_path"]).unlink(missing_ok=True)
        (self.temp_dir / f"{session_id}.json").unlink(missing_ok=True)
        self.sessions.pop(session_id, None)
        return True

    def cleanup_expired_sessions(self):
        """Clean up expired upload sessions"""
        now = datetime.now(UTC)
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
    
    def _generate_session_id(self) -> str:
        """Generate an unguessable session ID.

        Was a sha256 of filename + size + timestamp, all of which an attacker
        either supplies or can narrow to a second — a guessable handle on
        another tenant's in-flight upload (issue #454).
        """
        return secrets.token_urlsafe(32)
    
    def get_session(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """Get ``user_id``'s session from memory or disk.

        A session owned by someone else is returned as None, so callers answer
        404 for both "no such session" and "not yours" — a distinguishable
        response would confirm another tenant's session id exists (issue #454).
        """
        if not _SESSION_ID_RE.match(session_id):
            return None

        session = self.sessions.get(session_id)
        if session is None:
            metadata_path = self.temp_dir / f"{session_id}.json"
            if not metadata_path.exists():
                return None
            with open(metadata_path) as f:
                session = json.load(f)
            self.sessions[session_id] = session

        if session.get("user_id") != user_id:
            return None
        return session
    
    def _save_session_metadata(self, session_id: str, session: dict[str, Any]):
        """Save session metadata to disk for recovery"""
        metadata_path = self.temp_dir / f"{session_id}.json"
        with open(metadata_path, 'w') as f:
            json.dump(session, f)
    
    def _calculate_progress(self, session: dict[str, Any]) -> float:
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
        self.request_times: dict[str, list[datetime]] = {}  # user_id -> [timestamps]
        self.active_uploads: dict[str, int] = {}  # user_id -> count
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        now = datetime.now(UTC)
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
        self.request_times[user_id].append(datetime.now(UTC))
    
    def start_upload(self, user_id: str):
        """Record upload start"""
        if user_id not in self.active_uploads:
            self.active_uploads[user_id] = 0
        self.active_uploads[user_id] += 1
    
    def end_upload(self, user_id: str):
        """Record upload end"""
        if user_id in self.active_uploads:
            self.active_uploads[user_id] = max(0, self.active_uploads[user_id] - 1)