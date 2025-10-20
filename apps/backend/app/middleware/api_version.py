"""
API versioning middleware for handling version negotiation and routing.

Provides middleware to:
1. Parse Accept header for API version preferences
2. Route requests to appropriate versioned endpoints
3. Handle version mismatches and unsupported versions
4. Add deprecation warnings for legacy endpoints
"""

import logging
import re
from typing import Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Supported API versions
SUPPORTED_VERSIONS = ["v1"]
CURRENT_VERSION = "v1"
DEFAULT_VERSION = "v1"

# Version header pattern: application/vnd.narrativeml.v1+json
VERSION_PATTERN = re.compile(r"application/vnd\.narrativeml\.v(\d+)\+json")


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API versioning through Accept headers and URL paths.

    Features:
    - Parse Accept header for version preference
    - Default to v1 if no version specified
    - Return 406 Not Acceptable for unsupported versions
    - Add deprecation warnings to responses
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and add version handling."""

        # Extract version from Accept header
        requested_version = self._parse_version_from_header(request)

        # Extract version from URL path
        # Handle both request.path (direct) and request.url.path (starlette)
        path = request.url.path if hasattr(request, 'url') else request.path
        path_version = self._parse_version_from_path(path)

        # Determine which version to use
        version = path_version or requested_version or DEFAULT_VERSION

        # Validate version is supported
        if version not in SUPPORTED_VERSIONS:
            return JSONResponse(
                status_code=406,
                content={
                    "error": "Not Acceptable",
                    "message": f"API version '{version}' is not supported",
                    "supported_versions": SUPPORTED_VERSIONS,
                    "current_version": CURRENT_VERSION,
                },
            )

        # Add version info to request state for route handlers
        request.state.api_version = version

        # Process request
        response = await call_next(request)

        # Add version headers to response
        response.headers["X-API-Version"] = version
        response.headers["X-API-Current-Version"] = CURRENT_VERSION

        # Add deprecation warning if using old version
        if version != CURRENT_VERSION:
            response.headers[
                "Warning"
            ] = f'299 - "API version {version} is deprecated. Please upgrade to {CURRENT_VERSION}"'
            response.headers["Deprecation"] = "true"

        return response

    def _parse_version_from_header(self, request: Request) -> Optional[str]:
        """
        Parse API version from Accept header.

        Looks for pattern: application/vnd.narrativeml.v1+json

        Returns:
            Version string (e.g., "v1") or None if not found
        """
        accept_header = request.headers.get("Accept", "")

        match = VERSION_PATTERN.search(accept_header)
        if match:
            version_number = match.group(1)
            return f"v{version_number}"

        return None

    def _parse_version_from_path(self, path: str) -> Optional[str]:
        """
        Parse API version from URL path.

        Looks for /api/v1/ or /api/v2/ patterns.

        Returns:
            Version string (e.g., "v1") or None if not found
        """
        # Match /api/v{number}/ pattern
        match = re.search(r"/api/(v\d+)/", path)
        if match:
            return match.group(1)

        return None


def get_api_version(request: Request) -> str:
    """
    Helper function to get API version from request state.

    Args:
        request: FastAPI request object

    Returns:
        API version string (e.g., "v1")
    """
    return getattr(request.state, "api_version", DEFAULT_VERSION)
