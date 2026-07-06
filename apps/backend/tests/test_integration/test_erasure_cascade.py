"""Zero-residual cascade erasure integration test (issue #259, AC1).

Seeds a dataset across BOTH id-spaces (DatasetMetadata string-`dataset_id` and
legacy UserData ObjectId) with children in each, plus an MLModel, then erases
and asserts **zero residuals** in every child collection, an append-only audit
entry, an accurate manifest, and idempotency on re-run.

Requires real MongoDB (the `setup_database` fixture). S3 is forced into mock
mode (see `_hermetic_s3`) so the test is fast and deterministic and never
touches real AWS — this test's job is the Mongo/PII zero-residual guarantee.
Live S3 object deletion is covered by DATA_ERASURE_AND_BACKUP_RUNBOOK.md and the
existing model_storage S3 tests.
"""

import pytest

from app.models.column_stats import ColumnStats
from app.models.dataset import DatasetMetadata
from app.models.erasure_audit import ErasureAuditLog
from app.models.ml_model import MLModel
from app.models.user_data import UserData
from app.models.version import DatasetVersion
from app.models.visualization_cache import VisualizationCache
from app.models.workflow import WorkflowState
from app.services.erasure_service import dataset_erasure_service

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "erasure_user_1"
DATASET_ID = "dataset_erasetest01"

# Build S3 URLs with the real configured bucket so model_storage's prefix-strip
# resolves the key correctly.
BUCKET = dataset_erasure_service.s3_service.bucket_name


@pytest.fixture(autouse=True)
def _hermetic_s3():
    """Force the erasure service's S3 into mock mode for the DB zero-residual test.

    The app S3Service reads real AWS creds from .env; without this the cascade
    would issue real DeleteObject calls (slow, non-deterministic). S3 key
    derivation is unit-tested (test_erasure_service.py) and the delete wiring
    reuses already-tested model_storage/S3Service paths; this test isolates the
    Mongo/PII zero-residual guarantee. Live S3 deletion is covered by the AC3
    restore/erasure drill in DATA_ERASURE_AND_BACKUP_RUNBOOK.md.
    """
    services = [
        dataset_erasure_service.s3_service,
        dataset_erasure_service.model_storage.s3_service,
    ]
    saved = [s.is_mock_mode for s in services]
    for s in services:
        s.is_mock_mode = True
    try:
        yield
    finally:
        for s, was in zip(services, saved, strict=True):
            s.is_mock_mode = was


async def _seed_string_space() -> None:
    """DatasetMetadata parent + string-`dataset_id` children + an MLModel."""
    await DatasetMetadata(
        user_id=USER,
        dataset_id=DATASET_ID,
        filename="d.csv",
        original_filename="d.csv",
        file_type="csv",
        file_path=f"datasets/{USER}/{DATASET_ID}_d.csv",
        s3_url=f"s3://{BUCKET}/datasets/{USER}/{DATASET_ID}_d.csv",
        num_rows=10,
        num_columns=3,
    ).insert()
    await WorkflowState(
        workflow_id="wf1", user_id=USER, dataset_id=DATASET_ID, current_stage="DATA_LOADING"
    ).insert()
    await DatasetVersion(
        version_id="v1",
        dataset_id=DATASET_ID,
        version_number=1,
        user_id=USER,
        content_hash="h",
        file_size=1,
        file_path="p",
        s3_url="s3://b/p",
        num_rows=10,
        num_columns=3,
        schema_hash="sh",
        created_by=USER,
    ).insert()
    await MLModel(
        user_id=USER,
        dataset_id=DATASET_ID,
        model_id="model1",
        name="m",
        problem_type="classification",
        algorithm="rf",
        target_column="y",
        feature_names=["a", "b"],
        cv_score=0.9,
        test_score=0.9,
        training_time=1.0,
        model_size=1,
        n_samples_train=10,
        n_features=2,
        model_path=f"s3://{BUCKET}/models/{USER}/model1/model.pkl",
    ).insert()


async def _seed_userdata_space() -> UserData:
    """Legacy UserData parent + Link[UserData] children (viz cache, column stats)."""
    ud = await UserData(
        user_id=USER,
        filename="legacy.csv",
        original_filename="legacy.csv",
        s3_url="s3://narrative-modeling-dev/uploads/legacy.csv",
        num_rows=5,
        num_columns=2,
        data_schema=[],
        contains_pii=True,
        pii_report={"emails": 3},
        data_preview=[{"email": "a@b.com"}],
    ).insert()
    await VisualizationCache(
        dataset_id=ud, visualization_type="histogram", data={"bins": [1, 2]}
    ).insert()
    await ColumnStats(
        dataset_id=ud, column_name="col1", data_type="numeric", count=5, missing=0, unique=5
    ).insert()
    return ud


async def _residual_counts(ud_id) -> dict[str, int]:
    """Count any surviving documents across every seeded collection."""
    return {
        "dataset_metadata": await DatasetMetadata.find(
            DatasetMetadata.dataset_id == DATASET_ID
        ).count(),
        "workflow_states": await WorkflowState.find(
            WorkflowState.dataset_id == DATASET_ID
        ).count(),
        "dataset_versions": await DatasetVersion.find(
            DatasetVersion.dataset_id == DATASET_ID
        ).count(),
        "ml_models": await MLModel.find(MLModel.dataset_id == DATASET_ID).count(),
        "user_data": await UserData.find(UserData.id == ud_id).count(),
        "visualization_cache": await VisualizationCache.find(
            {"dataset_id.$id": ud_id}
        ).count(),
        "column_stats": await ColumnStats.find({"dataset_id.$id": ud_id}).count(),
    }


async def test_erase_dataset_leaves_zero_residuals(setup_database):
    await _seed_string_space()
    ud = await _seed_userdata_space()

    # Sanity: everything seeded.
    before = await _residual_counts(ud.id)
    assert all(c >= 1 for c in before.values()), before

    # Erase the string-space dataset (its DatasetMetadata id).
    manifest_a = await dataset_erasure_service.erase_dataset(
        DATASET_ID, USER, actor_id=USER, reason="gdpr_request"
    )
    # Erase the legacy UserData dataset (its ObjectId).
    manifest_b = await dataset_erasure_service.erase_dataset(str(ud.id), USER, actor_id=USER)

    # AC1: zero residuals in EVERY collection.
    after = await _residual_counts(ud.id)
    assert after == {k: 0 for k in after}, after

    # Manifest is accurate (records what was swept).
    assert manifest_a.documents_deleted.get("dataset_metadata") == 1
    assert manifest_a.documents_deleted.get("ml_models") == 1
    assert manifest_a.documents_deleted.get("workflow_states") == 1
    assert not manifest_a.idempotent_noop
    assert manifest_b.documents_deleted.get("user_data") == 1
    assert manifest_b.documents_deleted.get("visualization_cache") == 1
    # No cascade failures (S3 is mocked; Mongo/Redis must all succeed).
    assert manifest_a.failures == [], manifest_a.failures
    assert manifest_b.failures == [], manifest_b.failures

    # AC2: append-only audit log has one immutable entry per erasure.
    audit = await ErasureAuditLog.find(ErasureAuditLog.subject_user_id == USER).to_list()
    assert len(audit) == 2
    assert {a.target_id for a in audit} == {DATASET_ID, str(ud.id)}
    assert all(a.reason in (None, "gdpr_request") for a in audit)

    # Idempotency: re-running finds nothing -> no-op manifest, no crash.
    again = await dataset_erasure_service.erase_dataset(DATASET_ID, USER, actor_id=USER)
    assert again.idempotent_noop
    assert again.total_documents_deleted == 0


async def test_erase_dataset_by_non_owner_is_noop(setup_database):
    """A caller who does not own the dataset erases NOTHING (cross-tenant guard)."""
    await _seed_string_space()
    ud = await _seed_userdata_space()

    # An attacker who knows the ids but owns neither.
    m1 = await dataset_erasure_service.erase_dataset(DATASET_ID, "attacker", actor_id="attacker")
    m2 = await dataset_erasure_service.erase_dataset(str(ud.id), "attacker", actor_id="attacker")

    assert m1.idempotent_noop and m1.total_documents_deleted == 0
    assert m2.idempotent_noop and m2.total_documents_deleted == 0
    # Victim's data is fully intact.
    after = await _residual_counts(ud.id)
    assert all(c >= 1 for c in after.values()), after


async def test_erase_user_sweeps_all_owned_datasets(setup_database):
    await _seed_string_space()
    ud = await _seed_userdata_space()

    manifest = await dataset_erasure_service.erase_user(USER, actor_id=USER, reason="account_deletion")

    after = await _residual_counts(ud.id)
    assert after == {k: 0 for k in after}, after
    assert not manifest.idempotent_noop
    # One aggregate audit entry for the whole-user erasure.
    audit = await ErasureAuditLog.find(
        ErasureAuditLog.target_type == "user", ErasureAuditLog.subject_user_id == USER
    ).to_list()
    assert len(audit) == 1
