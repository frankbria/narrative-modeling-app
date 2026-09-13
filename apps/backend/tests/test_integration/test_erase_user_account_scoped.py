"""#480 [P1.5]: erase_user must remove every account-scoped record.

Before #480 the user sweep stopped at models/jobs/feedback + dataset children,
leaving live API keys (which still authenticated the paid serving surface),
feature-store rows, saved recipes, quota counters and the local billing mirror
behind. This seeds one of each for a user, erases the user, and asserts:

- AC1: the API key no longer authenticates (the sharp one).
- AC2: feature-store (features, versions, collections) and recipes are gone.
- AC3: Subscription + UsageRecord are deleted, with a manifest note recording
  that Stripe stays the authoritative billing record.
- AC4: `verify_api_key` rejects the erased key.

Requires real MongoDB (setup_database). S3 stays in mock mode — no datasets are
seeded, so the cascade never touches S3.
"""

import pytest
from fastapi import HTTPException

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

USER = "erase_account_user"
OTHER = "other_tenant_user"


async def _seed() -> str:
    """Seed one account-scoped record of each kind. Returns the raw API key."""
    from beanie import PydanticObjectId

    from app.api.routes.production import hash_api_key
    from app.models.api_key import APIKey
    from app.models.feature_store import (
        FeatureCollection,
        FeatureVersion,
        StoredFeature,
    )
    from app.models.subscription import Subscription
    from app.models.usage import UsageRecord
    from app.services.transformation_engine.recipe_manager import (
        RecipeExecutionHistory,
        SharedRecipe,
        TransformationRecipe,
    )

    raw_key = "sk_live_erase_account_test_key_value_0123456789"
    await APIKey(
        key_id="key-erase-1", key_hash=hash_api_key(raw_key), name="k", user_id=USER, is_active=True
    ).insert()

    sf = await StoredFeature(
        feature_id="feat-1", user_id=USER, name="f", description="d", category="c",
        definition_type="transformation", definition_code="x", output_type="numeric",
        output_column_name="col", created_by=USER,
    ).insert()
    await FeatureVersion(
        version_id="fv-1", feature_id=sf.feature_id, version_number=1, definition_code="x",
        definition_type="transformation", output_type="numeric", changes_description="init",
        created_by=USER,
    ).insert()
    await FeatureCollection(
        collection_id="fc-1", user_id=USER, name="c", description="d", domain="finance",
        created_by=USER,
    ).insert()

    await TransformationRecipe(name="r", user_id=USER, steps=[]).insert()
    await RecipeExecutionHistory(
        recipe_id=PydanticObjectId(), user_id=USER, dataset_id="ds1", success=True,
        rows_affected=1, execution_time_ms=5,
    ).insert()
    await SharedRecipe(
        name="r", user_id=USER, original_recipe_id=PydanticObjectId(),
        original_owner_id=OTHER, steps=[],
    ).insert()

    await UsageRecord(user_id=USER, period_key="2026-09", metric="uploads", units=3).insert()
    await Subscription(user_id=USER).insert()
    return raw_key


async def test_erase_user_removes_all_account_scoped_records(setup_database):
    from app.api.routes.production import verify_api_key
    from app.models.api_key import APIKey
    from app.models.feature_store import (
        FeatureCollection,
        FeatureVersion,
        StoredFeature,
    )
    from app.models.subscription import Subscription
    from app.models.usage import UsageRecord
    from app.services.erasure_service import dataset_erasure_service
    from app.services.transformation_engine.recipe_manager import (
        RecipeExecutionHistory,
        SharedRecipe,
        TransformationRecipe,
    )

    raw_key = await _seed()

    # AC1/AC4 precondition: the key authenticates before erasure.
    doc = await verify_api_key(raw_key)
    assert doc.user_id == USER

    manifest = await dataset_erasure_service.erase_user(USER, actor_id=USER, reason="gdpr_request")

    # AC1/AC2/AC3: nothing account-scoped survives for this user.
    assert await APIKey.find(APIKey.user_id == USER).count() == 0
    assert await StoredFeature.find(StoredFeature.user_id == USER).count() == 0
    assert await FeatureVersion.find(FeatureVersion.feature_id == "feat-1").count() == 0
    assert await FeatureCollection.find(FeatureCollection.user_id == USER).count() == 0
    assert await TransformationRecipe.find(TransformationRecipe.user_id == USER).count() == 0
    assert await RecipeExecutionHistory.find(RecipeExecutionHistory.user_id == USER).count() == 0
    assert await SharedRecipe.find(SharedRecipe.user_id == USER).count() == 0
    assert await UsageRecord.find(UsageRecord.user_id == USER).count() == 0
    assert await Subscription.find(Subscription.user_id == USER).count() == 0

    # AC3: the billing-retention decision is recorded, not silent.
    assert any("Stripe" in n for n in manifest.notes), manifest.notes
    assert manifest.documents_deleted.get("api_keys") == 1
    assert manifest.documents_deleted.get("subscriptions") == 1

    # AC4: the erased key no longer authenticates.
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(raw_key)
    assert exc.value.status_code == 401


async def test_erase_user_does_not_touch_another_tenants_records(setup_database):
    """The sweep is scoped by user_id — a co-tenant's records survive."""
    from app.api.routes.production import hash_api_key
    from app.models.api_key import APIKey
    from app.services.erasure_service import dataset_erasure_service

    await _seed()
    await APIKey(
        key_id="key-other", key_hash=hash_api_key("sk_live_other_tenant_key_valueeeeeeeeeeeeee"),
        name="k", user_id=OTHER, is_active=True,
    ).insert()

    await dataset_erasure_service.erase_user(USER, actor_id=USER)

    assert await APIKey.find(APIKey.user_id == OTHER).count() == 1
