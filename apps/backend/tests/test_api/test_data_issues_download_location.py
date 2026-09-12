"""#466: every `data_issues.py` handler hands the downloader a URL, never a raw key.

The router is mounted nowhere today (#471), so there is no HTTP path to it; the handlers
are called directly. Every lookup is stubbed with the shapes the handlers read, and the
download itself is stubbed to record its argument and stop the handler right there.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.api.routes import data_issues as routes
from app.schemas.data_issue import (
    BatchFixRequest,
    FixApplicationRequest,
    FixPreviewRequest,
    IssueDetectionRequest,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("beanie_models_initialized")]

USER = "u1"
DS = str(ObjectId())
EXPECTED = f"s3://test-bucket/datasets/{USER}/ds_f.csv"


def _user_data() -> MagicMock:
    # a fresh upload: raw key in file_path, URL in s3_url
    return MagicMock(user_id=USER, file_path=f"datasets/{USER}/ds_f.csv", s3_url=EXPECTED)


def _record() -> MagicMock:
    fix = MagicMock(fix_id="fx", is_safe=True)
    issue = MagicMock(issue_id="i1", suggested_fixes=[fix])
    return MagicMock(issues=[issue])


CALLS = [
    ("detect", lambda: routes.detect_issues(IssueDetectionRequest(dataset_id=DS), USER)),
    ("preview_fix", lambda: routes.preview_fix(FixPreviewRequest(dataset_id=DS, issue_id="i1"), USER)),
    ("apply_fix[preview]", lambda: routes.apply_fix(
        FixApplicationRequest(dataset_id=DS, issue_id="i1", preview_mode=True), USER)),
    ("apply_fix", lambda: routes.apply_fix(
        FixApplicationRequest(dataset_id=DS, issue_id="i1", preview_mode=False), USER)),
    ("batch_apply_fixes", lambda: routes.batch_apply_fixes(
        BatchFixRequest(dataset_id=DS, issue_ids=["i1"], preview_mode=False), USER)),
]


@pytest.mark.parametrize("label, call", CALLS, ids=[c[0] for c in CALLS])
async def test_the_downloader_receives_a_url_not_a_raw_key(label, call):
    seen: list[str] = []

    async def stop(url, *args, **kwargs):
        seen.append(url)
        raise RuntimeError("stop here")

    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=_user_data()), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=_record()), \
         patch.object(routes, "get_dataframe_from_s3", side_effect=stop), \
         patch.dict("os.environ", {"AWS_S3_BUCKET": "test-bucket"}):
        try:
            await call()  # the handlers wrap the stop in their own error response or HTTPException
        except Exception:  # noqa: BLE001 — anything after the download is not under test here
            pass

    assert seen == [EXPECTED], f"{label}: downloader got {seen}"
