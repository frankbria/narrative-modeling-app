"""
TDD tests for the in-app feedback collection API route (issue #152).

Endpoint under test:
- POST /api/v1/feedback   store user feedback (201), validation (422), auth (401/403)

Auth fixture maps to user "test_user_123".
"""

import pytest


VALID_PAYLOAD = {
    "rating": 4,
    "category": "general",
    "message": "The onboarding flow was clear and easy to follow.",
    "page_context": "/onboarding",
}


@pytest.mark.integration
class TestSubmitFeedback:
    @pytest.mark.asyncio
    async def test_submit_returns_201_with_record(
        self, async_authorized_client, setup_database
    ):
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=VALID_PAYLOAD
        )

        assert response.status_code == 201
        data = response.json()
        assert data["feedback_id"].startswith("fb_")
        assert data["user_id"] == "test_user_123"
        assert data["rating"] == 4
        assert data["category"] == "general"
        assert data["message"] == VALID_PAYLOAD["message"]
        assert data["page_context"] == "/onboarding"
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_submit_persists_to_storage(
        self, async_authorized_client, setup_database
    ):
        """The feedback document is actually written to MongoDB (AC3)."""
        from app.models.feedback import Feedback

        response = await async_authorized_client.post(
            "/api/v1/feedback", json=VALID_PAYLOAD
        )
        assert response.status_code == 201
        feedback_id = response.json()["feedback_id"]

        stored = await Feedback.find_one(Feedback.feedback_id == feedback_id)
        assert stored is not None
        assert stored.user_id == "test_user_123"
        assert stored.rating == 4
        assert stored.category == "general"
        assert stored.message == VALID_PAYLOAD["message"]

    @pytest.mark.asyncio
    async def test_category_defaults_to_general(
        self, async_authorized_client, setup_database
    ):
        payload = {"rating": 5, "message": "Loved it!"}
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=payload
        )
        assert response.status_code == 201
        assert response.json()["category"] == "general"

    @pytest.mark.asyncio
    async def test_page_context_optional(
        self, async_authorized_client, setup_database
    ):
        payload = {"rating": 3, "category": "bug", "message": "Found a glitch."}
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=payload
        )
        assert response.status_code == 201
        assert response.json()["page_context"] is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("rating", [0, 6, -1, 10])
    async def test_rating_out_of_range_rejected(
        self, async_authorized_client, setup_database, rating
    ):
        payload = {**VALID_PAYLOAD, "rating": rating}
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=payload
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_message_rejected(
        self, async_authorized_client, setup_database
    ):
        payload = {**VALID_PAYLOAD, "message": ""}
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=payload
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_category_rejected(
        self, async_authorized_client, setup_database
    ):
        payload = {**VALID_PAYLOAD, "category": "spam"}
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=payload
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_rating_rejected(
        self, async_authorized_client, setup_database
    ):
        payload = {"category": "general", "message": "No rating here."}
        response = await async_authorized_client.post(
            "/api/v1/feedback", json=payload
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_requires_auth(self, async_test_client, setup_database):
        response = await async_test_client.post(
            "/api/v1/feedback", json=VALID_PAYLOAD
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_storage_failure_returns_opaque_500(
        self, async_authorized_client, setup_database
    ):
        """A storage error returns a 500 without leaking internal details."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "app.models.feedback.Feedback.insert",
            new=AsyncMock(side_effect=RuntimeError("mongodb://secret@host failed")),
        ):
            response = await async_authorized_client.post(
                "/api/v1/feedback", json=VALID_PAYLOAD
            )

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "secret" not in detail
        assert "mongodb" not in detail.lower()
