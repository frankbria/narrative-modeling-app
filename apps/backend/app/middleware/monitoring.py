"""
Monitoring middleware for FastAPI
Automatically tracks API calls and performance
"""

import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.monitoring import monitor


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically track API metrics"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Extract endpoint info
        endpoint = request.url.path
        method = request.method

        # Initialize variables to ensure they're always defined for finally block
        status_code = 500  # Default to 500 for exceptions
        response = None

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

        except Exception as e:
            # Set status code for exception case
            status_code = 500

            # Track errors
            monitor.increment('api.exceptions', 1, {
                'endpoint': endpoint,
                'method': method,
                'exception': type(e).__name__
            })
            raise

        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Record metrics (status_code is always defined now)
            monitor.record_api_call(endpoint, method, status_code, duration)

        return response