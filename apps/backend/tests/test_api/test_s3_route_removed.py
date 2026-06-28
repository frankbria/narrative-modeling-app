"""Regression test for #252 (P0.2).

The unauthenticated `GET /api/v1/s3/s3/upload-url` endpoint minted presigned
S3 PUT URLs with a client-controlled Key (arbitrary bucket write -> model.pkl
overwrite -> RCE). It had no callers and was deleted rather than hardened, so
the route must not be registered at all.
"""

from app.main import app


def test_s3_upload_url_route_is_not_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any("upload-url" in path for path in paths)
    assert "/api/v1/s3/s3/upload-url" not in paths
