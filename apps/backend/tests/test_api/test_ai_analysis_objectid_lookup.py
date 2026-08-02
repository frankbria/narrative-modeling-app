"""The /ai/analyze and /ai/summarize lookups against a real Mongo document (#409).

`UserData.id` is a `PydanticObjectId`; the routes received `file_id` as a `str` from
the path and compared the two directly, so the query matched nothing and every call
404'd "File not found" — the AI Insights panel's entire backend.

The existing suite in `test_ai_analysis.py` cannot see this: it patches
`UserData.find_one` wholesale, so the comparison under test never runs and a
hand-written `return_value` stands in for the query. These tests insert a real
document and let Beanie build the query, which is the only way the coercion is
exercised.

Same trap, same fix as `model_training.py:297-304`, which carries a comment about
it — this is the third place it has appeared.

Every test takes `setup_database`, which clears the collections around each case.
Without it the inserted `UserData` documents outlive the module and make later
suites order-dependent — the same class of leak as the `prediction_log` and
metrics-gauge residue noted in CLAUDE.md.
"""

import pytest
from beanie import PydanticObjectId

from app.models.user_data import UserData

# Must match `async_authorized_client`'s dependency override in conftest.py.
TEST_USER = "test_user_123"


async def _seed_user_data(user_id: str = TEST_USER, processed: bool = True) -> UserData:
    doc = UserData(
        user_id=user_id,
        filename="churn.csv",
        original_filename="churn.csv",
        file_path=f"uploads/{user_id}/churn.csv",
        s3_url="s3://test-bucket/churn.csv",
        num_rows=2,
        num_columns=2,
        data_schema=[],
        is_processed=processed,
        data_preview=[{"age": 41, "churned": 0}, {"age": 22, "churned": 1}],
    )
    await doc.insert()
    return doc


@pytest.mark.asyncio
class TestAiAnalysisObjectIdLookup:
    async def test_summarize_finds_a_document_by_its_string_id(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        """The panel sends the id as a path string; it must still resolve."""
        doc = await _seed_user_data()

        async def _fake_summary(*_args, **_kwargs):
            return {
                "summary": "Two columns, mostly numeric.",
                "key_insights": ["age skews young"],
                "recommendations": ["collect more rows"],
                "data_quality_assessment": {"score": 0.9},
            }

        monkeypatch.setattr(
            "app.services.dataset_summarization.dataset_summarization_service."
            "generate_comprehensive_summary",
            _fake_summary,
        )

        response = await async_authorized_client.post(
            f"/api/v1/ai/summarize/{doc.id}"
        )

        # Scoped to the lookup, deliberately. Pre-fix this was 404 "File not found"
        # for a document that plainly exists; anything past the lookup belongs to
        # the summarization service and its own suite. Asserting 200 here would
        # couple this file to that service's internals for no extra signal.
        assert response.json().get("detail") != "File not found", response.json()
        assert response.status_code != 404, response.json()

    async def test_analyze_finds_a_document_by_its_string_id(
        self, async_authorized_client, setup_database, monkeypatch
    ):
        doc = await _seed_user_data()

        async def _fake_analysis(*_args, **_kwargs):
            from app.services.mcp_integration import MCPAnalysisResponse

            return MCPAnalysisResponse(
                success=True,
                analysis={"rows": 2},
                insights=["small sample"],
                recommendations=[],
            )

        monkeypatch.setattr(
            "app.services.mcp_integration.mcp_service.analyze_dataset",
            _fake_analysis,
        )

        response = await async_authorized_client.post(f"/api/v1/ai/analyze/{doc.id}")

        # Same scoping as the summarize case above.
        assert response.json().get("detail") != "File not found", response.json()
        assert response.status_code != 404, response.json()

    async def test_unprocessed_document_still_reports_400_not_404(
        self, async_authorized_client, setup_database
    ):
        """The is_processed guard is only reachable once the lookup works."""
        doc = await _seed_user_data(processed=False)

        response = await async_authorized_client.post(
            f"/api/v1/ai/summarize/{doc.id}"
        )

        assert response.status_code == 400, response.json()
        assert "must be processed" in response.json()["detail"]

    async def test_another_users_document_is_not_readable(
        self, async_authorized_client, setup_database
    ):
        """Coercing the id must not weaken the ownership filter."""
        doc = await _seed_user_data(user_id="somebody-else")

        response = await async_authorized_client.post(
            f"/api/v1/ai/summarize/{doc.id}"
        )

        assert response.status_code == 404

    async def test_a_non_objectid_string_is_a_clean_404(
        self, async_authorized_client, setup_database
    ):
        """A malformed id must 404, not raise InvalidId as a 500."""
        response = await async_authorized_client.post(
            "/api/v1/ai/summarize/not-an-object-id"
        )

        assert response.status_code == 404, response.json()

    async def test_a_valid_but_absent_objectid_is_a_404(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(
            f"/api/v1/ai/summarize/{PydanticObjectId()}"
        )

        assert response.status_code == 404
