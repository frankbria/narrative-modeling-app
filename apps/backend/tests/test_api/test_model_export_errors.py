"""#468: every export route maps the service's typed errors the same way.

NotFoundError (missing or another tenant's model) → 404; ExportFormatUnavailable (converter
or runtime not installed here) → 501; any other ValueError (conversion failed) → 400.
The service is stubbed at the route module's `export_service` seam; the real app, real auth
override, real 5xx sanitiser.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import model_export as routes
from app.auth.nextauth_auth import get_current_user_id
from app.main import app
from app.services.exceptions import NotFoundError
from app.services.model_export import ExportFormatUnavailable

ROUTES = [
    ("GET", "/api/v1/models/m1/export/python", "export_python_code"),
    ("GET", "/api/v1/models/m1/export/onnx", "export_model_onnx"),
    ("GET", "/api/v1/models/m1/export/pmml", "export_model_pmml"),
    ("GET", "/api/v1/models/m1/export/docker", "export_docker_container"),
    ("POST", "/api/v1/models/m1/export/python", "export_python_code"),
    ("POST", "/api/v1/models/m1/export/onnx", "export_model_onnx"),
    ("POST", "/api/v1/models/m1/export/pmml", "export_model_pmml"),
    ("POST", "/api/v1/models/m1/export/docker", "export_docker_container"),
]
ERRORS = [
    (NotFoundError(resource_type="Model", resource_id="m1"), 404),
    (ExportFormatUnavailable("not installed here"), 501),
    (ValueError("conversion failed"), 400),
]


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user_id] = lambda: "test_user_123"
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.parametrize("method, url, service_method", ROUTES, ids=[f"{m} {u.rsplit('/', 1)[1]}" for m, u, _ in ROUTES])
@pytest.mark.parametrize("error, status", ERRORS, ids=["not-found", "unavailable", "conversion"])
def test_service_errors_map_to_the_same_statuses(method, url, service_method, error, status):
    with patch.object(routes.export_service, service_method, new_callable=AsyncMock, side_effect=error):
        with TestClient(app) as client:
            response = client.request(method, url)
    assert response.status_code == status, f"{method} {url}: {response.status_code} {response.text}"
    if status == 404:
        assert "not found" in response.json()["detail"]
    if status == 501:
        assert response.json().get("request_id")  # sanitised 5xx body


HOSTILE = 'churn"; x=y\r\nX-Injected: 1_1.0'
CONTENT = {"export_python_code": "print(1)", "export_model_pmml": "<PMML/>"}


@pytest.mark.parametrize("method, url, service_method", ROUTES, ids=[f"{m} {u.rsplit('/', 1)[1]}" for m, u, _ in ROUTES])
def test_a_model_name_cannot_break_out_of_the_download_header(method, url, service_method):
    """#648: the filename is built from the model's name, which its owner chooses."""
    exported = (CONTENT.get(service_method, b"\x00bytes"), f"{HOSTILE}.bin")
    with patch.object(routes.export_service, service_method, new_callable=AsyncMock, return_value=exported):
        with TestClient(app) as client:
            response = client.request(method, url)

    assert response.status_code == 200, response.text
    disposition = response.headers["content-disposition"]
    assert "x-injected" not in response.headers
    assert "\r" not in disposition and "\n" not in disposition
    assert disposition.startswith('attachment; filename="churn; x=yX-Injected: 1_1.0.bin"; filename*=UTF-8\'\'')
    assert response.content == (exported[0].encode() if isinstance(exported[0], str) else exported[0])


def test_a_model_name_outside_ascii_still_downloads():
    exported = ("print(1)", "модель_1.0_inference.py")
    with patch.object(routes.export_service, "export_python_code", new_callable=AsyncMock, return_value=exported):
        with TestClient(app) as client:
            response = client.get("/api/v1/models/m1/export/python")

    assert response.status_code == 200, response.text
    assert "filename*=UTF-8''%D0%BC%D0%BE%D0%B4%D0%B5%D0%BB%D1%8C_1.0_inference.py" in response.headers["content-disposition"]


def test_an_unknown_format_is_refused_by_name():
    with TestClient(app) as client:
        response = client.post("/api/v1/models/m1/export/exe")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported export format: exe"


def test_custom_export_passes_its_options_on():
    exporter = AsyncMock(return_value=("print(1)", "m_1.0_inference.py"))
    with patch.object(routes.export_service, "export_python_code", exporter):
        with TestClient(app) as client:
            client.post("/api/v1/models/m1/export/python", json={"include_preprocessing": False})

    assert exporter.call_args.kwargs["include_preprocessing"] is False
