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
                              include_ai=False, read_cache=False)
    await svc.suggest_features(df=df, dataset_id=DATASET, user_id="u2",
                              include_ai=False, read_cache=False)
    assert svc._get_cache_key("u1", DATASET) != svc._get_cache_key("u2", DATASET)
    assert len(hermetic.store) == 2  # one entry per tenant, not shared
