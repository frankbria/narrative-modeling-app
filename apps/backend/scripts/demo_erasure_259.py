"""Demo: cascade dataset erasure + right-to-erasure (issue #259).

Runs against the TEST Mongo database. Seeds a dataset with children across
collections, then erases it and shows outcome evidence for each acceptance
criterion: zero residuals, an accurate manifest, an append-only audit entry,
idempotency, and the cross-tenant guard.

    cd apps/backend && ENVIRONMENT=test PYTHONPATH=. uv run python scripts/demo_erasure_259.py
"""

import asyncio

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models.dataset import DatasetMetadata
from app.models.erasure_audit import ErasureAuditLog
from app.models.ml_model import MLModel
from app.models.registry import DOCUMENT_MODELS
from app.models.workflow import WorkflowState
from app.services.erasure_service import dataset_erasure_service

USER = "demo_owner"
DS = "dataset_demo259"


def line(t):
    print("\n" + "=" * 68 + f"\n{t}\n" + "=" * 68)


async def counts():
    return {
        "dataset_metadata": await DatasetMetadata.find(DatasetMetadata.dataset_id == DS).count(),
        "workflow_states": await WorkflowState.find(WorkflowState.dataset_id == DS).count(),
        "ml_models": await MLModel.find(MLModel.dataset_id == DS).count(),
    }


async def seed():
    await DatasetMetadata(
        user_id=USER, dataset_id=DS, filename="d.csv", original_filename="d.csv",
        file_type="csv", file_path=f"datasets/{USER}/{DS}_d.csv",
        s3_url=f"s3://b/datasets/{USER}/{DS}_d.csv", num_rows=10, num_columns=3,
    ).insert()
    await WorkflowState(workflow_id="wf", user_id=USER, dataset_id=DS, current_stage="DATA_LOADING").insert()
    await MLModel(
        user_id=USER, dataset_id=DS, model_id="m1", name="m", problem_type="classification",
        algorithm="rf", target_column="y", feature_names=["a"], cv_score=0.9, test_score=0.9,
        training_time=1.0, model_size=1, n_samples_train=10, n_features=1, model_path="s3://b/models/x",
    ).insert()


async def main():
    client = AsyncIOMotorClient(settings.TEST_MONGODB_URI)
    await init_beanie(database=client[settings.TEST_MONGODB_DB], document_models=DOCUMENT_MODELS)
    dataset_erasure_service.s3_service.is_mock_mode = True
    dataset_erasure_service.model_storage.s3_service.is_mock_mode = True
    for m in DOCUMENT_MODELS:
        await m.find().delete()

    line("SETUP — seed a dataset with children")
    await seed()
    print("Counts BEFORE erase:", await counts())

    line("AC1 — DELETE cascades: zero residuals + accurate manifest")
    manifest = await dataset_erasure_service.erase_dataset(DS, USER, actor_id=USER, reason="gdpr_request")
    print("Counts AFTER erase: ", await counts(), "  <-- all zero")
    print("Manifest.documents_deleted:", manifest.documents_deleted)
    print("Manifest.status:", manifest.status, "| failures:", manifest.failures)

    line("AC2 — append-only audit log recorded the erasure")
    audit = await ErasureAuditLog.find(ErasureAuditLog.target_id == DS).to_list()
    for a in audit:
        print(f"audit: actor={a.actor_id} subject={a.subject_user_id} target={a.target_id} "
              f"reason={a.reason} status={a.status} docs={a.manifest['documents_deleted']}")

    line("AC1 — idempotent: re-erasing a gone dataset is a safe no-op")
    again = await dataset_erasure_service.erase_dataset(DS, USER, actor_id=USER)
    print("idempotent_noop:", again.idempotent_noop, "| documents_deleted:", again.total_documents_deleted)

    line("SECURITY — a non-owner erases nothing (cross-tenant guard)")
    await seed()
    print("Counts BEFORE attacker call:", await counts())
    attack = await dataset_erasure_service.erase_dataset(DS, "attacker", actor_id="attacker")
    print("Attacker manifest -> noop:", attack.idempotent_noop, "deleted:", attack.total_documents_deleted)
    print("Counts AFTER attacker call:", await counts(), "  <-- victim data intact")

    for m in DOCUMENT_MODELS:
        await m.find().delete()
    client.close()
    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
