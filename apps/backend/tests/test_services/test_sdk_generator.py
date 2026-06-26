"""Unit tests for the SDKGenerator (issue #86).

Pure/stateless generators — no DB, no IO. Asserts every SDK carries the real
production serving contract and the model's actual feature names.
"""

import ast
import json

import pytest

from app.services.sdk_generator import SUPPORTED_LANGUAGES, SDKGenerator

ENDPOINT = "http://localhost:8000/api/v1/production/v1/models/m1"


@pytest.fixture
def gen() -> SDKGenerator:
    return SDKGenerator(
        model_id="m1",
        model_name="Sales Prediction Model",
        feature_names=["month", "store_id"],
        problem_type="regression",
        serving_endpoint=ENDPOINT,
    )


def test_class_name_pascalcase(gen):
    assert gen.class_name == "SalesPredictionModelClient"


def test_class_name_handles_empty_and_leading_digit():
    # Empty name AND empty id → generic fallback.
    assert SDKGenerator(
        model_id="", model_name="", feature_names=[], problem_type="x",
        serving_endpoint=ENDPOINT,
    ).class_name == "ModelClient"
    assert SDKGenerator(
        model_id="m", model_name="123 model", feature_names=[], problem_type="x",
        serving_endpoint=ENDPOINT,
    ).class_name == "Model123ModelClient"


def test_sample_record_uses_feature_names(gen):
    assert gen.sample_record() == {"month": 0, "store_id": 0}


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_every_language_has_real_contract(gen, language):
    source = gen.get(language)
    assert source is not None
    # The base URL and "/predict" are concatenated at runtime, so assert both.
    assert "/api/v1/production/v1/models/m1" in source
    assert "/predict" in source
    assert "X-API-Key" in source
    assert "month" in source  # real feature in the sample


def test_get_unknown_language_returns_none(gen):
    assert gen.get("ruby") is None


def test_python_sdk_is_valid_python(gen):
    # Smoke-parse: the generated Python must at least be syntactically valid.
    ast.parse(gen.python_sdk())


def test_postman_collection_is_valid_and_per_deployment(gen):
    collection = gen.postman_collection()
    # Round-trips through JSON (Postman import requires valid JSON).
    json.dumps(collection)
    assert "Sales Prediction Model" in collection["info"]["name"]
    raw = collection["item"][0]["request"]["body"]["raw"]
    # The predict body is itself valid JSON carrying the real sample record.
    assert json.loads(raw)["data"] == [{"month": 0, "store_id": 0}]


def test_info_payload(gen):
    info = gen.info()
    assert info["predict_url"] == f"{ENDPOINT}/predict"
    assert info["languages"] == list(SUPPORTED_LANGUAGES)
    assert "X-API-Key" in info["auth"]


def test_framework_samples_include_webhook_receiver(gen):
    samples = gen.framework_samples()
    assert {"flask", "fastapi", "express", "nextjs", "webhook_receiver"} <= set(samples)
    receiver = samples["webhook_receiver"]
    assert "X-Signature" in receiver and "hmac" in receiver


def test_readme_documents_features_and_auth(gen):
    readme = gen.readme("python")
    assert "X-API-Key" in readme
    assert "month" in readme
    assert "pip install requests" in readme
