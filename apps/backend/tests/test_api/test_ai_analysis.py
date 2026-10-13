"""
The two AI routes that are deliberately not implemented.

The analyze and summarize routes are tested against real documents in
`test_ai_analyze_real_document.py` and `test_ai_summarize_real_document.py`. They were
tested here with a `MagicMock` dataset behind a patched lookup, which hid a summary that
failed and a fallback that was charged (#981, #683).
"""

import pytest


class TestAIAnalysisAPI:
    """Test suite for the AI stubs"""

    @pytest.mark.asyncio
    async def test_chat_not_implemented(self, authorized_client):
        """Chat is a stub — it must reject with 501, not a fake 'coming soon' 200 (#274).

        The #269 5xx sanitizer replaces the body with a generic "Not implemented"
        (the redirect hint lives in the OpenAPI docstring), so the fake canned
        response can no longer reach the client.
        """
        response = authorized_client.post("/api/v1/ai/chat/test-file-123")

        assert response.status_code == 501
        detail = response.json()["detail"]
        assert detail == "Not implemented"
        # The old canned placeholder must be gone.
        assert "will be implemented soon" not in detail

    @pytest.mark.asyncio
    async def test_cached_insights_not_implemented(self, authorized_client):
        """Cached insights are a stub — 501, not a misleading 200 (#274)."""
        response = authorized_client.get("/api/v1/ai/insights/test-file-123")

        assert response.status_code == 501
        assert response.json()["detail"] == "Not implemented"
