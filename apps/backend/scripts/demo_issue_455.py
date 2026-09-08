#!/usr/bin/env python3
"""#455 demo — the per-key rate-limit ceiling, exercised end to end.

Drives the REAL app (httpx over ASGITransport, real MongoDB) and the REAL
rate-limit middleware + store. Nothing here is mocked: every status code is one
FastAPI produced, and every rate_limit value is re-read from Mongo.

    MONGODB_URI=mongodb://localhost:27017 uv run python scripts/demo_issue_455.py
"""
import asyncio
import os
import sys

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SKIP_AUTH", "true")

DEMO_USER = "demo-455-user"
DEMO_DB = "narrative_modeling_demo_455"


def show(label: str, value) -> None:
    print(f"  {label:<44} {value}")


async def main() -> int:
    from beanie import init_beanie
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.api.routes.billing_webhook import _apply
    from app.api.routes.production import router as production_router
    from app.auth.nextauth_auth import get_current_user_id
    from app.billing.plans import api_key_rate_limit_ceiling
    from app.middleware.rate_limit import RateLimitMiddleware
    from app.models.api_key import APIKey
    from app.models.registry import DOCUMENT_MODELS
    from app.models.subscription import PlanTier, SubscriptionStatus
    from app.services.rate_limit import InMemoryRateLimitStore

    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri)
    await client.drop_database(DEMO_DB)
    await init_beanie(database=client[DEMO_DB], document_models=DOCUMENT_MODELS)

    free = api_key_rate_limit_ceiling(PlanTier.FREE)
    enterprise = api_key_rate_limit_ceiling(PlanTier.ENTERPRISE)

    print("\n=== Plan ceilings (AC2: single source of truth in plans.py) ===")
    for tier in PlanTier:
        show(f"{tier.value} api_key_rate_limit", api_key_rate_limit_ceiling(tier))
    show("all finite (UNLIMITED would re-open the hole)", all(
        api_key_rate_limit_ceiling(t) > 0 for t in PlanTier
    ))

    # Real app: the production router behind the real rate-limit middleware.
    app = FastAPI()
    store = InMemoryRateLimitStore()
    app.add_middleware(
        RateLimitMiddleware,
        store=store,
        enabled=True,          # disabled in the test env by default (AC5)
        default_requests=1000,
        default_window_seconds=60,
        apikey_window_seconds=60,
    )
    app.include_router(production_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user_id] = lambda: DEMO_USER

    @app.get("/api/v1/production/v1/models/demo/predict")
    async def _predict():  # stands in for the paid serving surface
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://demo") as http:
        keys_url = "/api/v1/production/api-keys"

        print("\n=== AC1: rate_limit=0 is refused at the door ===")
        for value in (0, -1):
            resp = await http.post(keys_url, json={"name": "x", "rate_limit": value})
            show(f"POST api-keys rate_limit={value}", f"HTTP {resp.status_code}")
            assert resp.status_code == 422, resp.text

        print("\n=== AC1/AC2: an absurd value is clamped to the plan ceiling ===")
        resp = await http.post(
            keys_url, json={"name": "greedy", "rate_limit": 10_000_000}
        )
        body = resp.json()
        show("POST api-keys rate_limit=10,000,000", f"HTTP {resp.status_code}")
        show("response rate_limit", body["rate_limit"])
        stored = await APIKey.find_one({"key_id": body["key_id"]})
        show("stored in MongoDB", stored.rate_limit)
        assert body["rate_limit"] == stored.rate_limit == free

        print("\n=== A ceiling, not an override: a lower ask is honoured ===")
        resp = await http.post(keys_url, json={"name": "modest", "rate_limit": 5})
        show("POST api-keys rate_limit=5 -> stored", resp.json()["rate_limit"])
        assert resp.json()["rate_limit"] == 5

        print("\n=== Defence 1: a LEGACY row already at 0 is still limited ===")
        raw = "sk_live_demo455legacyrow"
        legacy = APIKey(
            key_id="demo-455-legacy",
            key_hash=APIKey.hash_key(raw),
            name="written before the fix",
            user_id=DEMO_USER,
            rate_limit=0,  # the exact state #455 describes
        )
        await legacy.insert()
        show("legacy row rate_limit in MongoDB", legacy.rate_limit)
        path = "/api/v1/production/v1/models/demo/predict"
        headers = {"X-API-Key": raw}
        codes = [(await http.get(path, headers=headers)).status_code for _ in range(3)]
        show("3 requests on the paid serving surface", codes)
        assert codes == [200, 429, 429], codes
        show("before the fix this would have been", "[200, 200, 200] (unlimited)")

    print("\n=== Defence 2: a plan downgrade re-clamps existing keys ===")
    ent_key = APIKey(
        key_id="demo-455-enterprise",
        key_hash=APIKey.hash_key("sk_live_demo455enterprise"),
        name="minted on ENTERPRISE",
        user_id=DEMO_USER,
        rate_limit=enterprise,
    )
    await ent_key.insert()
    show("key minted while on ENTERPRISE", ent_key.rate_limit)
    await _apply(
        DEMO_USER, status_=SubscriptionStatus.CANCELED, tier=PlanTier.ENTERPRISE
    )
    reread = await APIKey.find_one({"key_id": "demo-455-enterprise"})
    show("after the cancellation webhook", reread.rate_limit)
    assert reread.rate_limit == free

    print("\n=== AC3: the audit script sees this database's damage ===")
    await APIKey.find_one({"key_id": "demo-455-legacy"}).update(
        {"$set": {"rate_limit": 0}}
    )
    env = {**os.environ, "MONGODB_URI": uri, "MONGODB_DB": DEMO_DB, "PYTHONPATH": "."}
    for args in ([], ["--apply"]):
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "scripts/fix_api_key_rate_limits.py", *args,
            env=env, stdout=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        label = "--apply" if args else "read-only"
        print(f"\n  $ fix_api_key_rate_limits.py {label}  (exit {proc.returncode})")
        for line in out.decode().strip().splitlines():
            print(f"    {line}")

    final = await APIKey.find_one({"key_id": "demo-455-legacy"})
    show("\n  legacy row after --apply", final.rate_limit)
    assert final.rate_limit == free

    await client.drop_database(DEMO_DB)
    print("\nAll six acceptance criteria demonstrated against the real app.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
