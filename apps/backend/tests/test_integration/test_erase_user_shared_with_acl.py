"""#662 [P1.45]: erase_user must pull the erased user's id from OTHER tenants'
feature-store ACLs (StoredFeature/FeatureCollection.shared_with).

#480 scrubbed the id from SharedRecipe.original_owner_id, but the same id can sit in
another tenant's `shared_with` list (a feature shared to the erased user, or one they
granted others). The user_id sweep only removes docs the erased user OWNS, so the id
lingered. This seeds a co-tenant's feature + collection listing the erased user, erases
the user, and asserts the id is pulled while the co-tenant's docs survive.

Requires real MongoDB (setup_database); no datasets seeded so S3 stays untouched.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ERASED = "erase_acl_user"
OTHER = "other_acl_tenant"


async def test_erase_user_pulls_id_from_co_tenant_shared_with(setup_database):
    from app.models.feature_store import FeatureCollection, StoredFeature
    from app.services.erasure_service import DatasetErasureService

    # A co-tenant's feature + collection that share access WITH the erased user.
    await StoredFeature(
        feature_id="feat-other", user_id=OTHER, name="f", description="d", category="c",
        definition_type="transformation", definition_code="x", output_type="numeric",
        output_column_name="col", created_by=OTHER, shared_with=[ERASED, "third_user"],
    ).insert()
    await FeatureCollection(
        collection_id="coll-other", user_id=OTHER, name="c", description="d",
        domain="finance", created_by=OTHER, shared_with=[ERASED, "third_user"],
    ).insert()

    manifest = await DatasetErasureService().erase_user(
        ERASED, actor_id=ERASED, reason="gdpr_request"
    )

    # The co-tenant's docs SURVIVE (their data), but no longer name the erased user;
    # the unrelated grantee stays.
    sf = await StoredFeature.find_one(StoredFeature.feature_id == "feat-other")
    coll = await FeatureCollection.find_one(FeatureCollection.collection_id == "coll-other")
    assert sf is not None and coll is not None, "co-tenant docs must not be deleted"
    assert ERASED not in sf.shared_with and "third_user" in sf.shared_with
    assert ERASED not in coll.shared_with and "third_user" in coll.shared_with
    assert manifest.failures == [], manifest.failures
    # Recorded on the manifest (AC1).
    assert any("shared_with" in n for n in manifest.notes), manifest.notes
