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


@pytest.mark.parametrize("label, call", CALLS, ids=[c[0] for c in CALLS])
async def test_a_dataset_with_no_stored_location_is_a_400_not_a_swallowed_error(label, call):
    """claude-review: the accessor raises ValueError for "nothing stored"; every handler must
    surface that as its 400, not let it fall into the generic handler as a 200 {success: false}."""
    from fastapi import HTTPException

    empty = MagicMock(user_id=USER, file_path=None, s3_url=None)
    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=empty), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=_record()), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock) as download:
        with pytest.raises(HTTPException) as exc:
            await call()
    assert exc.value.status_code == 400, label
    download.assert_not_called()


async def test_batch_apply_moves_the_dataset_and_its_twin():
    """#467/#627: after applying fixes the handler used to set `user_data.file_path` alone;
    it must move both twins through `record_new_file` with the uploaded URL."""
    import pandas as pd

    applied = MagicMock(issue_id="i1", fix_id="fx", success=True, rows_affected=1, error_message=None)
    engine = MagicMock()
    engine.apply_batch_fixes = AsyncMock(return_value=(pd.DataFrame({"a": [1, 2]}), [applied], []))
    record = _record()
    record.save = AsyncMock()
    user_data = _user_data()
    new_url = f"s3://test-bucket/transformed/{USER}/ds_fixed.parquet"

    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=user_data), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=record), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock, return_value=pd.DataFrame({"a": [1, 2]})), \
         patch.object(routes, "FixSuggestionEngine", return_value=engine), \
         patch.object(routes, "upload_dataframe_to_s3", new_callable=AsyncMock, return_value=new_url), \
         patch.object(routes, "record_new_file", new_callable=AsyncMock) as move, \
         patch.dict("os.environ", {"AWS_S3_BUCKET": "test-bucket"}):
        response = await routes.batch_apply_fixes(
            BatchFixRequest(dataset_id=DS, issue_ids=["i1"], preview_mode=False), USER
        )

    assert response.success is True, response
    move.assert_awaited_once_with(user_data, new_url)
    assert user_data.num_rows == 2


async def test_apply_fix_moves_the_dataset_and_its_twin():
    """#467/#627: the non-preview apply path must move both twins through `record_new_file`."""
    import pandas as pd

    applied = MagicMock(issue_id="i1", fix_id="fx", success=True, rows_affected=1, error_message=None)
    engine = MagicMock()
    engine.apply_fix = MagicMock(return_value=(pd.DataFrame({"a": [1, 2, 3]}), applied))
    record = _record()
    record.save = AsyncMock()
    user_data = _user_data()
    new_url = f"s3://test-bucket/transformed/{USER}/ds_fixed.parquet"

    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=user_data), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=record), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock, return_value=pd.DataFrame({"a": [1, 2, 3]})), \
         patch.object(routes, "FixSuggestionEngine", return_value=engine), \
         patch.object(routes, "upload_dataframe_to_s3", new_callable=AsyncMock, return_value=new_url), \
         patch.object(routes, "record_new_file", new_callable=AsyncMock) as move, \
         patch.dict("os.environ", {"AWS_S3_BUCKET": "test-bucket"}):
        response = await routes.apply_fix(
            FixApplicationRequest(dataset_id=DS, issue_id="i1", preview_mode=False), USER
        )

    assert response.success is True, response
    move.assert_awaited_once_with(user_data, new_url)
    assert user_data.num_rows == 3
