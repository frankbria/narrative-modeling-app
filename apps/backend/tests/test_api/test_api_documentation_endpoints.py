"""#512: the documentation endpoints serve the live description, and the
hand-written client libraries for endpoints that never existed are gone."""

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1/docs"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_openapi_json_is_served_for_this_instance(client):
    response = client.get(f"{API}/openapi.json")

    assert response.status_code == 200
    spec = response.json()
    assert spec["servers"] == [{"url": "http://testserver", "description": "This instance"}]
    assert "/api/v1/ml/train" in spec["paths"]
    assert "## Rate limits" in spec["info"]["description"]


def test_openapi_yaml_is_the_same_document(client):
    response = client.get(f"{API}/openapi.yaml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-yaml")
    assert yaml.safe_load(response.text) == client.get(f"{API}/openapi.json").json()


@pytest.mark.parametrize(
    "path",
    ["clients/python", "clients/javascript", "clients/curl", "integrations/flask", "postman"],
)
def test_the_hand_written_sdk_surface_is_gone(client, path):
    """It published clients for `/models/train` and `/data/upload`, which no route serves."""
    assert client.get(f"{API}/{path}").status_code == 404
    assert f"{API}/{path.split('/')[0]}" not in " ".join(client.get(f"{API}/openapi.json").json()["paths"])


def test_the_interactive_docs_still_load(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
