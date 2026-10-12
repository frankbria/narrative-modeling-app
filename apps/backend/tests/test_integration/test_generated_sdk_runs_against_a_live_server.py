"""#512 AC3: the generated SDK is run against a running instance.

A generated client is only honest if it reaches a real endpoint. The hand-written
SDK this issue removed targeted `/models/train` and `/data/upload`, which no route
serves, and nothing ever executed it. This test starts the backend as its own
process, uploads a file and trains a model through the API, fetches the Python
client the API generates for that model, executes that source, and predicts with it.

It needs MongoDB and LocalStack (the model artifact is stored and loaded for real).
"""

import contextlib
import io
import os
import random
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from pymongo import MongoClient

from tests.api_tokens import TEST_SECRET, mint_api_token

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[2]
USER = "sdk-smoke-user"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _training_csv() -> bytes:
    rng = random.Random(512)
    rows = ["plan,spend,churned"]
    for _ in range(300):
        plan, spend = rng.choice(["basic", "pro", "premium"]), rng.uniform(10, 200)
        rows.append(f"{plan},{spend:.1f},{int(plan == 'basic' or spend < 40)}")
    return ("\n".join(rows) + "\n").encode()


@pytest.fixture
def live_server(test_s3_bucket):
    """The backend on a free port, with real auth, its own database and a real bucket."""
    port = _free_port()
    mongo_uri = os.getenv("TEST_MONGODB_URI", "mongodb://localhost:27017").rsplit("/", 1)[0]
    if not mongo_uri.startswith("mongodb"):
        mongo_uri = "mongodb://localhost:27017"
    database = f"narrative_modeling_sdk_smoke_{port}"
    env = {
        **os.environ,
        "ENVIRONMENT": "test",
        "SKIP_AUTH": "false",
        "NEXTAUTH_SECRET": TEST_SECRET,
        "MONGODB_URI": mongo_uri,
        "MONGODB_DB": database,
        "TEST_MONGODB_DB": database,
        "AWS_ENDPOINT_URL": os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"),
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_REGION": "us-east-1",
        "AWS_S3_BUCKET": test_s3_bucket,
        "AWS_BUCKET_NAME": test_s3_bucket,
        "S3_BUCKET_NAME": test_s3_bucket,
        "OPENAI_API_KEY": "",
        "PYTHONPATH": str(BACKEND),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"the server exited while starting:\n{proc.stdout.read()[-2000:]}")
            with contextlib.suppress(httpx.HTTPError):
                if httpx.get(f"{base}/health/ready", timeout=2).status_code == 200:
                    break
            time.sleep(0.5)
        else:
            pytest.fail("the server did not become ready within 90s")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()  # a server that ignores SIGTERM must not outlive the test
            proc.wait(timeout=15)
        with contextlib.suppress(Exception):
            MongoClient(mongo_uri, serverSelectionTimeoutMS=2000).drop_database(database)


def _wait_for_model(session: httpx.Client, model_id: str) -> None:
    """Training runs in the background of a real server; the model exists when it ends."""
    deadline = time.time() + 180
    while time.time() < deadline:
        if session.get(f"/ml/{model_id}/sdk").status_code == 200:
            return
        time.sleep(1)
    logs = session.get(f"/ml/{model_id}/logs", params={"limit": 20}).text
    pytest.fail(f"the model was not trained within 180s; training log: {logs[-1500:]}")


def test_the_generated_python_client_predicts_against_a_running_server(live_server):
    session = httpx.Client(
        base_url=f"{live_server}/api/v1",
        headers={"Authorization": f"Bearer {mint_api_token(USER)}"},
        timeout=180,
    )
    upload = session.post("/upload/secure", files={"file": ("churn.csv", io.BytesIO(_training_csv()), "text/csv")})
    assert upload.status_code == 200 and "file_id" in upload.json(), upload.text
    train = session.post(
        "/ml/train",
        json={
            "dataset_id": upload.json()["file_id"],
            "target_column": "churned",
            "training_config": {"training_mode": "quick"},
        },
    )
    assert train.status_code == 200, train.text
    model_id = train.json()["model_id"]
    _wait_for_model(session, model_id)

    info = session.get(f"/ml/{model_id}/sdk").json()
    source = session.get(f"/ml/{model_id}/sdk/python")
    key = session.post("/production/api-keys", json={"name": "sdk smoke", "model_ids": [model_id]})
    assert source.status_code == 200 and key.status_code == 200, (source.text, key.text)

    # The serving URL the SDK was generated with is this server's own route.
    assert info["serving_endpoint"] == f"{live_server}/api/v1/production/v1/models/{model_id}"

    namespace: dict = {"__name__": "generated_sdk"}  # not "__main__": skip the file's demo call
    exec(compile(source.text, "generated_sdk.py", "exec"), namespace)  # noqa: S102 - our own generated code
    client_class = next(
        value for name, value in namespace.items() if isinstance(value, type) and hasattr(value, "predict")
    )
    client = client_class(api_key=key.json()["api_key"])  # the endpoint is the generated default

    result = client.predict([info["sample_record"], {"plan": "basic", "spend": 20.0}])

    assert len(result["predictions"]) == 2
    assert result["predictions"][1] == 1  # a basic plan churns in the training file
    assert client.info()["problem_type"].endswith("classification")
