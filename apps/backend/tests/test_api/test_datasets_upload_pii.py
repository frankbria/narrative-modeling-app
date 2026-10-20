"""`POST /datasets/upload` scans for PII like `/upload/secure` does (#1124).

It used to store every file unscanned, so `GET /datasets` listed a CSV with an email column
as `contains_pii: false` -- a PII result nobody computed (the defect #1121 removed from the
legacy `POST /upload/`). Now the stored report is the detector's: a name-only match (medium)
is stored and listed as PII; matching values (high) are refused before the S3 put, pointing
at `/upload/secure`, whose confirmation gate is the only way to store high-risk data.

Real Mongo documents, exact statuses. The S3 stand-in records its calls.
"""

import glob
import os

import pandas as pd
import pytest

from app.api.routes import datasets as datasets_module
from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData
from app.services.security.pii_detector import PIIDetector

pytestmark = pytest.mark.asyncio

HIGH_RISK_CSV = b"id,email\n1,alice@example.com\n2,bob@example.com\n"
NAME_ONLY_CSV = b"id,email\n1,x\n2,y\n"
CLEAN_CSV = b"a,b\n1,2\n3,4\n"


@pytest.fixture
def s3_puts(monkeypatch):
    puts: list[str] = []

    def fake_upload(file_content, s3_filename, content_type=None):
        puts.append(s3_filename)
        return True, f"s3://test-bucket/{s3_filename}"

    monkeypatch.setattr(datasets_module, "upload_file_to_s3", fake_upload)
    return puts


async def _upload(client, content: bytes):
    return await client.post(
        "/api/v1/datasets/upload", files={"file": ("people.csv", content, "text/csv")}
    )


async def _listed(client) -> dict:
    listing = await client.get("/api/v1/datasets")
    assert listing.status_code == 200, listing.text
    (item,) = listing.json()["datasets"]
    return item


async def test_high_risk_pii_is_refused_before_anything_is_stored(
    async_authorized_client, setup_database, s3_puts
):
    response = await _upload(async_authorized_client, HIGH_RISK_CSV)

    assert response.status_code == 400, response.text
    assert "/upload/secure" in response.json()["detail"]
    assert s3_puts == []
    assert await DatasetMetadata.find().count() == 0
    assert await UserData.find().count() == 0


async def test_a_name_only_match_is_stored_with_its_report_and_listed_as_pii(
    async_authorized_client, setup_database, s3_puts
):
    response = await _upload(async_authorized_client, NAME_ONLY_CSV)

    assert response.status_code == 200, response.text
    dataset = await DatasetMetadata.find_one(
        DatasetMetadata.dataset_id == response.json()["dataset_id"]
    )
    assert dataset.pii_report.contains_pii is True
    assert dataset.pii_report.risk_level == "medium"
    assert dataset.pii_report.pii_fields == ["email"]
    twin = await UserData.find_one(UserData.user_id == dataset.user_id)
    assert twin.contains_pii is True and twin.pii_risk_level == "medium"
    assert (await _listed(async_authorized_client))["contains_pii"] is True


async def test_a_clean_file_carries_a_computed_clean_report(
    async_authorized_client, setup_database, s3_puts
):
    response = await _upload(async_authorized_client, CLEAN_CSV)

    assert response.status_code == 200, response.text
    dataset = await DatasetMetadata.find_one(
        DatasetMetadata.dataset_id == response.json()["dataset_id"]
    )
    assert dataset.pii_report is not None, "a scan that found nothing still leaves its report"
    assert dataset.pii_report.contains_pii is False
    assert (await _listed(async_authorized_client))["contains_pii"] is False


async def test_the_shipped_onboarding_samples_have_no_high_risk_column():
    """The sample loader stores `contains_pii=False` without a scan: these files ship in
    the image and are synthetic. A medium hit is the detector matching a column NAME
    (`phone_service`, `zipcode`); a high one would mean real values were added."""
    samples = glob.glob(
        os.path.join(os.path.dirname(datasets_module.__file__), "..", "..", "sample_datasets", "*.csv")
    )
    assert samples, "the sample directory moved; update this guard"
    detector = PIIDetector()
    for path in samples:
        report = detector.generate_pii_report(detector.detect_pii_in_dataframe(pd.read_csv(path)))
        assert report["risk_level"] != "high", f"{os.path.basename(path)}: {report['detections']}"
