"""Integration tests for the AI orchestration endpoints (issue #89).

Covers /recommend-tools, /optimize-parameters, /feedback against a real test
MongoDB: recommendations, ownership 404s, feedback persistence, and the
feedback-driven personalization loop. No OpenAI key required (rule-based core).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.ai_feedback import AIRecommendationFeedback
from app.models.data_issue import (
    DataIssue,
    DataIssueRecord,
    IssueSeverity,
    IssueType,
)
from app.models.dataset import DatasetMetadata, SchemaField

TEST_USER = "test_user_123"


async def _seed_dataset(dataset_id: str, user_id: str = TEST_USER) -> None:
    metadata = DatasetMetadata(
        user_id=user_id,
        dataset_id=dataset_id,
        filename="data.csv",
        original_filename="data.csv",
        file_type="csv",
        file_path=f"datasets/{user_id}/{dataset_id}/data.csv",
        s3_url=f"s3://test-bucket/{dataset_id}.csv",
        num_rows=1000,
        num_columns=4,
        columns=["age", "income", "city", "user_id"],
        is_processed=True,
        data_schema=[
            SchemaField(
                field_name="age",
                field_type="numeric",
                inferred_dtype="int64",
                unique_values=80,
                missing_values=50,
            ),
            SchemaField(
                field_name="income",
                field_type="numeric",
                inferred_dtype="float64",
                unique_values=900,
                missing_values=0,
            ),
            SchemaField(
                field_name="city",
                field_type="categorical",
                inferred_dtype="object",
                unique_values=12,
                missing_values=0,
            ),
            SchemaField(
                field_name="user_id",
                field_type="categorical",
                inferred_dtype="object",
                unique_values=1000,
                missing_values=0,
                is_high_cardinality=True,
            ),
        ],
    )
    await metadata.insert()


@pytest.mark.integration
class TestRecommendTools:
    @pytest.mark.asyncio
    async def test_recommend_returns_recommendations_and_pipeline(
        self, async_authorized_client, setup_database
    ):
        await _seed_dataset("ds_rec_1")
        resp = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "ds_rec_1", "objective": "feature_engineering"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendations"]
        assert data["pipeline_suggestion"]
        assert data["data_profile_summary"]
        assert data["reasoning_trace"]
        # rule_based when no key; hybrid when OpenAI enhancement is available.
        assert data["generated_by"] in ("rule_based", "hybrid")
        # Every recommendation carries a plain-language explanation (AC4).
        assert all(r["explanation"] for r in data["recommendations"])

    @pytest.mark.asyncio
    async def test_recommend_unknown_dataset_404(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "missing", "objective": "data_cleaning"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_recommend_foreign_dataset_404(
        self, async_authorized_client, setup_database
    ):
        await _seed_dataset("ds_foreign", user_id="someone_else")
        resp = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "ds_foreign", "objective": "data_cleaning"},
        )
        assert resp.status_code == 404


@pytest.mark.integration
class TestInferredSchemaFallback:
    @pytest.mark.asyncio
    async def test_recommends_from_inferred_schema_when_data_schema_empty(
        self, async_authorized_client, setup_database
    ):
        """The /datasets upload path stores data_schema=[] + inferred_schema (codex)."""
        await DatasetMetadata(
            user_id=TEST_USER,
            dataset_id="ds_inferred",
            filename="d.csv",
            original_filename="d.csv",
            file_type="csv",
            file_path="d/ds_inferred.csv",
            s3_url="s3://b/ds_inferred.csv",
            num_rows=2000,
            num_columns=3,
            columns=["age", "city", "user_id"],
            is_processed=True,
            data_schema=[],
            inferred_schema={
                "columns": [
                    {"name": "age", "data_type": "integer", "cardinality": 70, "null_count": 0},
                    {"name": "city", "data_type": "categorical", "cardinality": 10, "null_count": 0},
                    {"name": "user_id", "data_type": "string", "cardinality": 2000, "null_count": 0},
                ]
            },
        ).insert()
        resp = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "ds_inferred", "objective": "feature_engineering"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["partial"] is False
        tool_types = {r["tool_type"] for r in data["recommendations"]}
        # age (numeric) -> standardize; city (low-card) -> one_hot; user_id (high-card) -> label
        assert "standardize" in tool_types
        assert "one_hot_encode" in tool_types
        assert "label_encode" in tool_types


@pytest.mark.integration
class TestOptimizeParameters:
    @pytest.mark.asyncio
    async def test_optimize_returns_params(
        self, async_authorized_client, setup_database
    ):
        await _seed_dataset("ds_opt_1")
        resp = await async_authorized_client.post(
            "/api/v1/ai/optimize-parameters",
            json={"dataset_id": "ds_opt_1", "tool_type": "fill_missing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["optimized_parameters"]["method"] == "median"
        assert data["explanation"]

    @pytest.mark.asyncio
    async def test_optimize_unknown_dataset_404(
        self, async_authorized_client, setup_database
    ):
        resp = await async_authorized_client.post(
            "/api/v1/ai/optimize-parameters",
            json={"dataset_id": "missing", "tool_type": "scale"},
        )
        assert resp.status_code == 404


@pytest.mark.integration
class TestUsesLatestIssueRecord:
    @pytest.mark.asyncio
    async def test_recommendations_use_newest_detection_run(
        self, async_authorized_client, setup_database
    ):
        """A second, newer DataIssueRecord supersedes the older one (codex fix)."""
        await _seed_dataset("ds_issues")
        now = datetime.now(UTC)
        # Old run: no duplicates.
        await DataIssueRecord(
            dataset_id="ds_issues",
            user_id=TEST_USER,
            issues=[],
            detected_at=now - timedelta(hours=1),
        ).insert()
        # New run: duplicates detected -> should drive a REMOVE_DUPLICATES rec.
        await DataIssueRecord(
            dataset_id="ds_issues",
            user_id=TEST_USER,
            issues=[
                DataIssue(
                    issue_id="i1",
                    issue_type=IssueType.DUPLICATES,
                    severity=IssueSeverity.HIGH,
                    description="dupes",
                )
            ],
            detected_at=now,
        ).insert()

        resp = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "ds_issues", "objective": "data_cleaning"},
        )
        assert resp.status_code == 200
        top = resp.json()["recommendations"][0]
        assert top["tool_type"] == "remove_duplicates"


@pytest.mark.integration
class TestFeedbackAndPersonalization:
    @pytest.mark.asyncio
    async def test_feedback_persists(self, async_authorized_client, setup_database):
        resp = await async_authorized_client.post(
            "/api/v1/ai/feedback",
            json={
                "recommendation_id": "rec_abc",
                "tool_type": "standardize",
                "action": "accepted",
                "rating": 5,
            },
        )
        assert resp.status_code == 201
        feedback_id = resp.json()["feedback_id"]
        stored = await AIRecommendationFeedback.find_one(
            AIRecommendationFeedback.feedback_id == feedback_id
        )
        assert stored is not None
        assert stored.action == "accepted"

    @pytest.mark.asyncio
    async def test_feedback_with_valid_dataset_201(
        self, async_authorized_client, setup_database
    ):
        await _seed_dataset("ds_fb_owned")
        resp = await async_authorized_client.post(
            "/api/v1/ai/feedback",
            json={
                "recommendation_id": "rec_y",
                "tool_type": "scale",
                "action": "accepted",
                "dataset_id": "ds_fb_owned",
            },
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_feedback_foreign_dataset_404(
        self, async_authorized_client, setup_database
    ):
        await _seed_dataset("ds_fb_foreign", user_id="someone_else")
        resp = await async_authorized_client.post(
            "/api/v1/ai/feedback",
            json={
                "recommendation_id": "rec_z",
                "tool_type": "scale",
                "action": "accepted",
                "dataset_id": "ds_fb_foreign",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rejection_personalizes_recommendations(
        self, async_authorized_client, setup_database
    ):
        await _seed_dataset("ds_personal")

        # Baseline: standardize is recommended for feature engineering.
        baseline = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "ds_personal", "objective": "feature_engineering"},
        )
        base_data = baseline.json()
        assert base_data["personalization_applied"] is False
        std_before = next(
            r["priority"] for r in base_data["recommendations"] if r["tool_type"] == "standardize"
        )

        # Reject "standardize" twice.
        for _ in range(2):
            await async_authorized_client.post(
                "/api/v1/ai/feedback",
                json={
                    "recommendation_id": "rec_x",
                    "tool_type": "standardize",
                    "action": "rejected",
                },
            )

        after = await async_authorized_client.post(
            "/api/v1/ai/recommend-tools",
            json={"dataset_id": "ds_personal", "objective": "feature_engineering"},
        )
        after_data = after.json()
        assert after_data["personalization_applied"] is True
        std_after = next(
            r["priority"] for r in after_data["recommendations"] if r["tool_type"] == "standardize"
        )
        assert std_after < std_before
