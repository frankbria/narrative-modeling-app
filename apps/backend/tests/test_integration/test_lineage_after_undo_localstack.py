"""#852: a transformation applied after an undo derives from the version the dataset
was actually at, not from the one that was undone.

The new version's parent was the dataset's highest version number. After apply, apply,
undo that is the undone step's version, so the lineage said the third result came from
data the user had just taken back. Through the routes against real S3 (LocalStack).
Skips locally when LocalStack is down; ``CI_REQUIRE_SERVICES`` makes that a failure.
"""
import io

import pytest

from app.models.transformation import TransformationConfig
from app.models.version import DatasetVersion
from tests.test_integration.test_charts_follow_a_transformation_localstack import (  # noqa: F401
    USER,
    client,
    real_s3_env,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

HISTORY = "/api/v1/transformations/datasets/{}/history"

# Every step below changes these bytes: a repeated row, padded text, a blank cell. A step
# that changed nothing would be stored as the version it started from (the same content
# is one version), and the lineage under test would not exist.
CSV = b"city,spend\n paris ,10\n paris ,10\nlyon,\n oslo ,30\nrome,40\n"


async def _apply(client, dataset_id: str, transformation_type: str) -> None:  # noqa: F811
    applied = await client.post(
        "/api/v1/transformations/apply",
        json={"dataset_id": dataset_id, "transformation_type": transformation_type, "parameters": {}},
    )
    assert applied.json()["success"] is True, applied.text


async def _step_versions() -> list[str | None]:
    config = await TransformationConfig.find_one(TransformationConfig.user_id == USER)
    return [step.version_id for step in config.transformation_steps]


async def test_a_step_applied_after_an_undo_derives_from_where_the_dataset_was(client):  # noqa: F811
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]

    await _apply(client, dataset_id, "remove_duplicates")
    await _apply(client, dataset_id, "trim_whitespace")
    first, undone = await _step_versions()
    assert (await client.post(HISTORY.format(dataset_id) + "/undo")).status_code == 200
    await _apply(client, dataset_id, "drop_missing")

    kept, third = await _step_versions()
    assert kept == first, "the history is the first step, then the new one"
    assert len({first, undone, third}) == 3, "each step changed the data, so each has its own version"
    version = await DatasetVersion.find_one(DatasetVersion.version_id == third)
    assert version.parent_version_id == first, "derived from the step the dataset was at"
    assert version.parent_version_id != undone


async def test_each_step_of_one_pipeline_derives_from_the_step_before_it(client):  # noqa: F811
    """The history's cursor does not move until every version of a pipeline is written,
    so the second step must not take the cursor's version for its parent too."""
    upload = await client.post("/api/v1/upload/secure", files={"file": ("visits.csv", io.BytesIO(CSV), "text/csv")})
    dataset_id = upload.json()["file_id"]
    await _apply(client, dataset_id, "remove_duplicates")

    applied = await client.post(
        "/api/v1/transformations/pipeline/apply",
        json={
            "dataset_id": dataset_id,
            "transformations": [
                {"type": "trim_whitespace", "parameters": {}},
                {"type": "drop_missing", "parameters": {}},
            ],
        },
    )
    assert applied.json()["success"] is True, applied.text

    first, second, third = await _step_versions()
    parents = {
        v.version_id: v.parent_version_id
        for v in await DatasetVersion.find(DatasetVersion.user_id == USER).to_list()
    }
    assert (parents[second], parents[third]) == (first, second)
