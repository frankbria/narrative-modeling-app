"""#522: a suggestion id from /suggest must be resolvable by apply/feedback/explain.

Before #522 those consumers keyed the suggestion cache on (dataset, auto, auto)
while /suggest keyed on (dataset, target, problem) and omitted user_id — so a
`/suggest` that specified a target_column handed out ids that every consumer then
404'd. The fix keys all of them on (user_id, dataset_id).
"""

import pandas as pd
import pytest

import app.api.routes.feature_engineering as fe_routes
import app.services.feature_engineering_service as fe_service


class _FakeCache:
    """In-memory stand-in for the Redis suggestion cache, so the round trip is
    exercised without Redis (the real cache degrades to a no-op when Redis is
    absent, which would make the ids unresolvable regardless of the key)."""

    def __init__(self):
        self.store: dict = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)


def _df():
    return pd.DataFrame({
        "amount": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "category": ["a", "b", "a", "b", "a", "b"],
        "created_at": pd.date_range("2024-01-01", periods=6, freq="D").astype(str),
        "target": [0, 1, 0, 1, 0, 1],
    })


@pytest.fixture
def hermetic(monkeypatch):
    """Fake cache + patched dataset loader so the routes run without Redis/S3."""
    cache = _FakeCache()
    monkeypatch.setattr(fe_service, "cache_service", cache)

    async def _load(dataset_id, user_id):
        return _df()

    monkeypatch.setattr(fe_routes, "_load_dataset_dataframe", _load)
    return cache


DATASET = "ds-522"


async def _suggest_with_target(client) -> list[dict]:
    """/suggest WITH a target_column — the exact case the old key mismatch broke."""
    resp = await client.post(
        f"/api/v1/datasets/{DATASET}/features/suggest",
        json={"target_column": "target", "problem_type": "binary_classification",
              "include_ai_suggestions": False},
    )
    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["suggestions"]
    assert suggestions, "expected at least one rule-based suggestion"
    return suggestions


@pytest.mark.asyncio
async def test_suggest_then_explain(setup_database, async_authorized_client, hermetic):
    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    resp = await async_authorized_client.get(
        f"/api/v1/datasets/{DATASET}/features/suggestions/{sid}"
    )
    assert resp.status_code == 200, resp.text  # not 404 — the id resolves


@pytest.mark.asyncio
async def test_suggest_then_feedback(setup_database, async_authorized_client, hermetic):
    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    resp = await async_authorized_client.post(
        f"/api/v1/features/suggestions/{sid}/feedback?dataset_id={DATASET}",
        json={"accepted": True},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_suggest_then_apply(setup_database, async_authorized_client, hermetic):
    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    resp = await async_authorized_client.post(
        f"/api/v1/datasets/{DATASET}/features/apply",
        json={"suggestion_id": sid},
    )
    assert resp.status_code == 200, resp.text
    assert "not found" not in resp.text.lower()


@pytest.mark.asyncio
async def test_feedback_does_not_download_the_dataset(
    setup_database, async_authorized_client, monkeypatch
):
    """#523: recording feedback must not load the dataset from S3 — it reads the
    suggestion from the cache /suggest wrote. The dataset loader is called once
    (by /suggest) and never again by feedback."""
    from unittest.mock import AsyncMock

    monkeypatch.setattr(fe_service, "cache_service", _FakeCache())
    loader = AsyncMock(return_value=_df())
    monkeypatch.setattr(fe_routes, "_load_dataset_dataframe", loader)

    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    assert loader.call_count == 1  # only /suggest loaded the dataset

    resp = await async_authorized_client.post(
        f"/api/v1/features/suggestions/{sid}/feedback?dataset_id={DATASET}",
        json={"accepted": True},
    )
    assert resp.status_code == 200, resp.text
    assert loader.call_count == 1  # feedback did NOT download the dataset


@pytest.mark.asyncio
async def test_suggest_more_keeps_the_original_batch_resolvable(
    setup_database, async_authorized_client, hermetic
):
    """#522 (review): /suggest-more must MERGE into the cached set, not replace it —
    the UI appends the new batch, so the original suggestions stay on screen and
    must still resolve for apply/feedback/explain."""
    original = await _suggest_with_target(async_authorized_client)
    orig_id = original[0]["id"]

    more = await async_authorized_client.post(
        f"/api/v1/datasets/{DATASET}/features/suggest-more",
        json={"count": 3, "excluded_suggestion_ids": [s["id"] for s in original]},
    )
    assert more.status_code == 200, more.text
    new_ids = [s["id"] for s in more.json()["suggestions"]]

    # The original id is STILL resolvable after suggest-more (was clobbered before).
    r_old = await async_authorized_client.get(
        f"/api/v1/datasets/{DATASET}/features/suggestions/{orig_id}"
    )
    assert r_old.status_code == 200, r_old.text
    # ...and so is a newly-added one.
    if new_ids:
        r_new = await async_authorized_client.get(
            f"/api/v1/datasets/{DATASET}/features/suggestions/{new_ids[0]}"
        )
        assert r_new.status_code == 200, r_new.text


@pytest.mark.asyncio
async def test_unknown_suggestion_id_is_404_not_500(
    setup_database, async_authorized_client, hermetic
):
    """AC3: an unknown/expired id is a clean 404."""
    await _suggest_with_target(async_authorized_client)
    resp = await async_authorized_client.get(
        f"/api/v1/datasets/{DATASET}/features/suggestions/does-not-exist"
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_cache_key_is_tenant_scoped(hermetic):
    """AC2: two tenants suggesting on the same dataset get separate cache entries,
    so one can never resolve the other's suggestion ids."""
    svc = fe_service.FeatureEngineeringService()
    df = _df()
    await svc.suggest_features(df=df, dataset_id=DATASET, user_id="u1",
                              include_ai=False)
    await svc.suggest_features(df=df, dataset_id=DATASET, user_id="u2",
                              include_ai=False)
    assert svc._get_cache_key("u1", DATASET) != svc._get_cache_key("u2", DATASET)
    assert len(hermetic.store) == 2  # one entry per tenant, not shared


# --- #728: a lookup reads the set /suggest handed out, and is not a model call ----------

TEST_USER = "test_user_123"


def _lookups(suggestion_id: str) -> list[tuple[str, str, dict | None]]:
    return [
        ("GET", f"/api/v1/datasets/{DATASET}/features/suggestions/{suggestion_id}", None),
        ("POST", f"/api/v1/datasets/{DATASET}/features/apply", {"suggestion_id": suggestion_id}),
        ("POST", f"/api/v1/datasets/{DATASET}/features/apply-multiple", {"suggestion_ids": [suggestion_id]}),
    ]


@pytest.mark.asyncio
async def test_looking_a_suggestion_up_costs_no_ai_call(setup_database, async_authorized_client, hermetic):
    from app.billing import metering

    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    # as stored after a /suggest the model took part in
    for cached in hermetic.store.values():
        cached["metadata"]["ai_used"] = True

    for method, url, body in _lookups(sid):
        resp = await async_authorized_client.request(method, url, json=body)
        assert resp.status_code == 200, resp.text

    assert await metering.usage_for(TEST_USER, "ai_calls") == 0


@pytest.mark.asyncio
async def test_a_tenant_out_of_ai_calls_can_still_use_what_they_were_given(
    setup_database, async_authorized_client, hermetic
):
    from app.billing import metering
    from app.billing.plans import PLAN_LIMITS, PlanTier

    limit = PLAN_LIMITS[PlanTier.FREE].ai_calls
    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    await metering.record(TEST_USER, "ai_calls", limit)
    assert await metering.usage_for(TEST_USER, "ai_calls") == limit

    for method, url, body in _lookups(sid):
        resp = await async_authorized_client.request(method, url, json=body)
        assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_an_expired_set_is_not_recomputed(setup_database, async_authorized_client, hermetic, monkeypatch):
    """Ids are minted per generation, so a fresh set can never hold the id asked for:
    recomputing bought a model call and still answered not found."""
    from unittest.mock import AsyncMock

    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    hermetic.store.clear()  # the hour passed
    recompute = AsyncMock(side_effect=AssertionError("a lookup must not generate suggestions"))
    monkeypatch.setattr(fe_service.feature_engineering_service, "suggest_features", recompute)

    explain, apply, apply_many = [
        await async_authorized_client.request(method, url, json=body) for method, url, body in _lookups(sid)
    ]

    assert explain.status_code == 404 and apply.status_code == 404
    assert apply_many.status_code == 200
    assert apply_many.json()["failed_features"] == [{"name": sid, "error": "Suggestion not found"}]
    recompute.assert_not_called()


@pytest.mark.asyncio
async def test_a_feature_that_cannot_be_previewed_is_reported_not_raised(
    setup_database, async_authorized_client, hermetic, monkeypatch
):
    from unittest.mock import AsyncMock

    sid = (await _suggest_with_target(async_authorized_client))[0]["id"]
    name = next(s["name"] for c in hermetic.store.values() for s in c["suggestions"] if s["id"] == sid)

    monkeypatch.setattr(fe_routes, "_apply_single_feature", AsyncMock(return_value=None))
    _, apply, apply_many = [
        await async_authorized_client.request(method, url, json=body) for method, url, body in _lookups(sid)
    ]
    assert apply.json()["failed_features"] == [
        {"name": name, "error": "Feature application not implemented for this type"}
    ]
    assert apply.json()["preview_data"] is None
    assert apply_many.json()["failed_features"] == [{"name": name, "error": "Feature application not implemented"}]

    monkeypatch.setattr(fe_routes, "_apply_single_feature", AsyncMock(side_effect=ValueError("no such column")))
    _, apply, apply_many = [
        await async_authorized_client.request(method, url, json=body) for method, url, body in _lookups(sid)
    ]
    assert apply.json()["failed_features"] == [{"name": name, "error": "no such column"}]
    assert apply_many.json()["failed_features"] == [{"name": name, "error": "no such column"}]


@pytest.mark.asyncio
async def test_a_previewed_feature_is_named_and_shown(setup_database, async_authorized_client, hermetic):
    suggestions = await _suggest_with_target(async_authorized_client)
    ids = [s["id"] for s in suggestions[:2]]

    resp = await async_authorized_client.post(
        f"/api/v1/datasets/{DATASET}/features/apply-multiple",
        json={"suggestion_ids": ids + ["gone"], "parameter_overrides": {ids[0]: {}}},
    )

    body = resp.json()
    assert resp.status_code == 200, resp.text
    assert {"name": "gone", "error": "Suggestion not found"} in body["failed_features"]
    assert body["new_column_count"] == len(body["applied_features"])
    assert body["message"].startswith(f"Previewed {len(body['applied_features'])} of 3 feature(s). Not saved")
    assert body["persisted"] is False


@pytest.mark.asyncio
async def test_more_suggestions_with_no_model_cost_no_ai_call(setup_database, async_authorized_client, hermetic):
    """No key is configured here, so the batch is rule-based: nothing was bought."""
    from app.billing import metering

    await _suggest_with_target(async_authorized_client)
    more = await async_authorized_client.post(
        f"/api/v1/datasets/{DATASET}/features/suggest-more", json={"count": 2}
    )

    assert more.status_code == 200, more.text
    assert more.json()["metadata"]["ai_used"] is False
    assert await metering.usage_for(TEST_USER, "ai_calls") == 0


@pytest.mark.asyncio
async def test_more_suggestions_from_the_model_cost_one(setup_database, async_authorized_client, hermetic, monkeypatch):
    from unittest.mock import AsyncMock

    from app.billing import metering

    monkeypatch.setattr(
        fe_service.feature_engineering_service, "_model_suggestions", AsyncMock(return_value=([], True))
    )
    more = await async_authorized_client.post(
        f"/api/v1/datasets/{DATASET}/features/suggest-more", json={"count": 2}
    )

    assert more.status_code == 200, more.text
    assert await metering.usage_for(TEST_USER, "ai_calls") == 1
