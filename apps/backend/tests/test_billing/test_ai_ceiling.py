"""Global daily AI spend ceiling (#768 AC2).

Per-tenant ``ai_calls`` quotas bound one account; nothing bounded N accounts. The
ceiling is one all-tenant, per-UTC-day counter of model calls, checked once per
logical call at the shared OpenAI circuit breaker. Past it, every call site raises
``AICeilingReached`` (a ``CircuitBreakerOpen``), so each service takes the
rule-based fallback it already has — and the routes, which key their
``enforcement.release`` on "did a model run", hand the tenant's unit back.
"""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.billing import ai_ceiling, metering
from app.middleware.metrics import ai_ceiling_denials
from app.utils.circuit_breaker import (
    AICeilingReached,
    CircuitBreakerOpen,
    with_circuit_breaker,
)

TEST_USER = "test_user_123"


def _denials() -> float:
    return ai_ceiling_denials._value.get()


async def _global_units() -> int:
    return await metering.usage_for(
        ai_ceiling.GLOBAL_TENANT, "ai_calls", period_key=ai_ceiling.day_key()
    )


class TestAdmit:
    async def test_admits_up_to_the_ceiling_then_denies(self, setup_database):
        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 2):
            assert await ai_ceiling.admit() is True
            assert await ai_ceiling.admit() is True
            before = _denials()
            assert await ai_ceiling.admit() is False
        assert await _global_units() == 2
        assert _denials() == before + 1

    async def test_denial_alerts_at_error(self, setup_database, caplog):
        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1), \
             patch.object(ai_ceiling, "_alerted_day", None):
            await ai_ceiling.admit()
            with caplog.at_level(logging.ERROR, logger="app.billing.ai_ceiling"):
                await ai_ceiling.admit()
        assert any("ceiling" in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)

    async def test_the_counter_is_per_utc_day(self, setup_database):
        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1):
            assert await ai_ceiling.admit() is True
            assert await ai_ceiling.admit() is False
            tomorrow = datetime(2099, 1, 2, tzinfo=UTC)
            with patch.object(ai_ceiling, "day_key", return_value=ai_ceiling.day_key(tomorrow)):
                assert await ai_ceiling.admit() is True

    async def test_does_not_touch_any_tenant_quota(self, setup_database):
        await ai_ceiling.admit()
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0
        # and the monthly global row does not exist — only the day row does
        assert await metering.usage_for(ai_ceiling.GLOBAL_TENANT, "ai_calls") == 0

    async def test_storage_failure_fails_closed(self, setup_database):
        from app.models.usage import UsageRecord

        with patch.object(UsageRecord, "get_motor_collection", side_effect=RuntimeError("mongo down")):
            assert await ai_ceiling.admit() is False


def test_the_default_is_the_budget_in_adr_003():
    from pathlib import Path

    adr = (
        Path(__file__).resolve().parents[4]
        / "docs/architecture/ADR-003-plan-limits-and-pricing.md"
    ).read_text()
    assert f"AI_CALLS_DAILY_CEILING` = {ai_ceiling.DEFAULT_DAILY_CEILING}" in adr


class TestBreakerChokePoint:
    async def test_openai_call_is_refused_past_the_ceiling(self, setup_database):
        model = AsyncMock(return_value="model output")

        @with_circuit_breaker("openai", max_attempts=3)
        async def call():
            return await model()

        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1):
            assert await call() == "model output"
            with pytest.raises(AICeilingReached) as exc:
                await call()
        assert isinstance(exc.value, CircuitBreakerOpen)  # every caller's fallback catches it
        assert model.await_count == 1

    async def test_retries_are_one_logical_call(self, setup_database):
        model = AsyncMock(side_effect=[RuntimeError("blip"), "ok"])

        @with_circuit_breaker("openai_issue_analyzer", max_attempts=2, max_wait_seconds=0)
        async def call():
            return await model()

        with patch("tenacity.nap.time.sleep"), patch("asyncio.sleep", new=AsyncMock()):
            assert await call() == "ok"
        assert await _global_units() == 1

    async def test_non_model_breakers_are_not_counted(self):
        # S3 shares the decorator; it must neither consult nor spend the ceiling
        # (no Beanie here — a lookup would fail closed and refuse the call).
        @with_circuit_breaker("s3")
        async def call():
            return "s3"

        with patch.object(ai_ceiling, "admit", new=AsyncMock(return_value=False)) as admit:
            assert await call() == "s3"
        admit.assert_not_awaited()


class TestServicesTakeTheirFallback:
    async def test_error_suggestions_fall_back_with_a_key_present(self, setup_database):
        """With a (fake) key the service would call the model; past the ceiling the
        breaker refuses before any network I/O and the rule-based suggestions are
        served as ``fallback`` — which is exactly what the ``/errors`` route keys its
        ``enforcement.release`` on (pinned in test_quota_enforcement)."""
        from app.services.error_analysis_service import ErrorAnalysisService
        from tests.test_services.test_error_analysis_service import (
            _classification_fixture,
        )

        service = ErrorAnalysisService()
        client = AsyncMock()
        service.client = client
        x, yt, yp, proba, labels, names = _classification_fixture()
        data = service.analyze(
            problem_type="classification", y_test=yt, y_pred=yp, y_proba=proba,
            class_labels=labels, x_test=x, feature_names=names,
        )
        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1):
            await ai_ceiling.admit()  # the day's budget is now spent
            suggestions, generated_by = await service.generate_suggestions(
                data, problem_type="classification", algorithm="Random Forest"
            )
        assert generated_by == "fallback"
        assert suggestions
        assert not client.mock_calls  # no model call was even attempted


class TestEveryModelCallIsBehindTheCeiling:
    """Registry: a ``chat.completions.create`` outside an ``openai*`` breaker would
    spend money the ceiling never sees. Walks ``app/`` like the metering registries."""

    def test_every_model_call_site_is_inside_a_model_breaker(self):
        import ast
        from pathlib import Path

        app_dir = Path(__file__).resolve().parents[2] / "app"

        def is_model_breaker(dec: ast.expr) -> bool:
            return (
                isinstance(dec, ast.Call)
                and getattr(dec.func, "id", None) == "with_circuit_breaker"
                and bool(dec.args)
                and isinstance(dec.args[0], ast.Constant)
                and str(dec.args[0].value).startswith("openai")
            )

        def calls_the_model(node: ast.AST) -> bool:
            return any(
                isinstance(n, ast.Attribute)
                and n.attr == "create"
                and isinstance(n.value, ast.Attribute)
                and n.value.attr == "completions"
                for n in ast.walk(node)
            )

        unguarded = []
        for path in app_dir.rglob("*.py"):
            tree = ast.parse(path.read_text())

            def visit(node: ast.AST, guarded: bool) -> None:
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        inner = guarded or any(map(is_model_breaker, child.decorator_list))
                        if not inner and calls_the_model(child) and not any(
                            isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
                            for c in ast.walk(child) if c is not child
                        ):
                            unguarded.append(f"{path.relative_to(app_dir)}::{child.name}")
                        visit(child, inner)
                    else:
                        visit(child, guarded)

            visit(tree, False)
        assert not unguarded, f"model calls outside an openai* breaker: {unguarded}"


class TestReleaseGaps:
    """Routes that used to keep the tenant's unit when no model ran (#768 review of
    the #461 fallbacks): `/ai/summarize` on its fallback, `/features/suggest` when
    the model call raised, `/ai/chat` when the ceiling refused it."""

    async def test_summarize_service_falls_back_past_the_ceiling(self, setup_database):
        from app.services.dataset_summarization import (
            DatasetSummarizationService,
            DatasetSummaryRequest,
        )

        service = DatasetSummarizationService()
        service.client = AsyncMock()
        request = DatasetSummaryRequest(
            file_id="f1", schema={"fields": []}, statistics={}, quality_report={}
        )
        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1):
            await ai_ceiling.admit()
            summary = await service.generate_comprehensive_summary(request)
        assert summary.model_used == "fallback"  # not an error summary naming the breaker
        service.client.chat.completions.create.assert_not_called()

    async def test_summarize_route_releases_on_a_fallback_summary(
        self, async_authorized_client, setup_database
    ):
        from app.services.dataset_summarization import (
            DatasetSummaryRequest,
            dataset_summarization_service,
        )
        from tests.test_api.test_ai_analysis_objectid_lookup import _seed_user_data

        doc = await _seed_user_data()
        doc.schema, doc.statistics, doc.quality_report = {}, {}, {}  # what processing writes
        await doc.save()
        service = dataset_summarization_service
        fallback = service._generate_fallback_summary(
            service._prepare_context(
                DatasetSummaryRequest(file_id="f", schema={}, statistics={}, quality_report={})
            )
        )
        with patch.object(
            dataset_summarization_service, "generate_comprehensive_summary",
            new=AsyncMock(return_value=fallback),
        ):
            response = await async_authorized_client.post(f"/api/v1/ai/summarize/{doc.id}")
        assert response.status_code == 200, response.text
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0

    async def test_feature_suggestions_report_no_ai_when_the_ceiling_refuses(self, setup_database):
        import pandas as pd

        from app.services.feature_engineering_service import FeatureEngineeringService

        df = pd.DataFrame({"a": range(20), "b": [x * 2.0 for x in range(20)], "y": [0, 1] * 10})
        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1), \
             patch("app.services.feature_engineering_service.get_openai_client",
                   return_value=AsyncMock()):
            await ai_ceiling.admit()
            response = await FeatureEngineeringService().suggest_features(
                df, "ds-1", target_column="y", user_id=TEST_USER, write_cache=False
            )
        assert response.metadata["ai_used"] is False

    async def test_chat_answers_503_and_refunds_past_the_ceiling(
        self, async_authorized_client, setup_database
    ):
        from app.services.ai_chat import ai_chat_service

        with patch.object(ai_ceiling, "AI_CALLS_DAILY_CEILING", 1), \
             patch.object(ai_chat_service, "client", AsyncMock()):
            await ai_ceiling.admit()
            response = await async_authorized_client.post(
                "/api/v1/ai/chat", json={"message": "hi", "context": "", "history": []}
            )
        assert response.status_code == 503  # body sanitised like every 5xx (#269)
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0

    async def test_chat_answers_503_and_refunds_when_the_breaker_is_open(
        self, async_authorized_client, setup_database
    ):
        """A genuinely open breaker (upstream failures, not the ceiling) takes the
        same refunded 503, rather than escaping as a 500."""
        from app.services.ai_chat import ai_chat_service

        with patch.object(
            ai_chat_service, "reply", new=AsyncMock(side_effect=CircuitBreakerOpen("openai", 60))
        ):
            response = await async_authorized_client.post(
                "/api/v1/ai/chat", json={"message": "hi", "context": "", "history": []}
            )
        assert response.status_code == 503
        assert await metering.usage_for(TEST_USER, "ai_calls") == 0
