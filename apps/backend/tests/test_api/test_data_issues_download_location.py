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
    DetectionOptions,
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
    issue = MagicMock(issue_id="i1", suggested_fixes=[fix], description="Missing values in a",
                      affected_column="a", affected_columns=[])
    return MagicMock(issues=[issue])


CALLS = [
    ("detect", lambda: routes.detect_issues(IssueDetectionRequest(dataset_id=DS, options=DetectionOptions(include_ai_analysis=False)), MagicMock(), USER)),
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


def _recorded_on(twin):
    """The fix routes' history recorder, stubbed: the twin they resolve and the recording."""
    return (
        patch.object(routes, "ensure_metadata_twin", new_callable=AsyncMock, return_value=twin),
        patch.object(routes.TransformationService, "record_edit", new_callable=AsyncMock,
                     return_value=f"s3://test-bucket/transformed/{USER}/ds_fixed.parquet"),
    )


async def test_batch_apply_records_one_history_step_on_the_twin():
    """#923: the fixes are one history step, recorded on the upload's twin, so undo
    restores the dataset as it was before them (#467/#627 moved both twins; #851 closed
    the history behind the move)."""
    import pandas as pd

    applied = MagicMock(issue_id="i1", fix_id="fx", success=True, rows_affected=1, error_message=None)
    engine = MagicMock()
    before, after = pd.DataFrame({"a": [1, None]}), pd.DataFrame({"a": [1, 2]})
    engine.apply_batch_fixes = AsyncMock(return_value=(after, [applied], []))
    record = _record()
    record.save = AsyncMock()
    twin = MagicMock()
    twin_patch, record_patch = _recorded_on(twin)

    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=_user_data()), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=record), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock, return_value=before), \
         patch.object(routes, "FixSuggestionEngine", return_value=engine), \
         twin_patch, record_patch as recorded:
        response = await routes.batch_apply_fixes(
            BatchFixRequest(dataset_id=DS, issue_ids=["i1"], preview_mode=False), USER
        )

    assert response.success is True, response
    assert response.new_version_id == f"s3://test-bucket/transformed/{USER}/ds_fixed.parquet"
    (dataset, user_id, frames), kwargs = recorded.await_args
    assert (dataset, user_id, frames) == (twin, USER, (before, after))
    assert kwargs["kind"] == "data_issue_fix" and kwargs["parameters"]["columns"] == ["a"]
    assert kwargs["description"] == "Fixed data issue: Missing values in a"
    record.save.assert_awaited_once()


async def test_apply_fix_records_one_history_step_on_the_twin():
    import pandas as pd

    applied = MagicMock(issue_id="i1", fix_id="fx", success=True, rows_affected=1, error_message=None)
    engine = MagicMock()
    before, after = pd.DataFrame({"a": [1, None, 3]}), pd.DataFrame({"a": [1, 2, 3]})
    engine.apply_fix = MagicMock(return_value=(after, applied))
    record = _record()
    record.save = AsyncMock()
    twin = MagicMock()
    twin_patch, record_patch = _recorded_on(twin)

    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=_user_data()), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=record), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock, return_value=before), \
         patch.object(routes, "FixSuggestionEngine", return_value=engine), \
         twin_patch, record_patch as recorded:
        response = await routes.apply_fix(
            FixApplicationRequest(dataset_id=DS, issue_id="i1", preview_mode=False), USER
        )

    assert response.success is True, response
    (dataset, user_id, frames), kwargs = recorded.await_args
    assert (dataset, user_id, frames) == (twin, USER, (before, after))
    assert kwargs["description"] == "Fixed data issue: Missing values in a"


async def test_a_fix_on_a_file_a_transformation_cannot_read_says_so():
    """The twin is refused for a type a transformation would misread (#857): the fix
    reports that reason instead of moving the dataset."""
    import pandas as pd

    from app.services.exceptions import NotFoundError

    engine = MagicMock()
    engine.apply_fix = MagicMock(return_value=(pd.DataFrame({"a": [1]}), MagicMock(rows_affected=1)))
    refused = NotFoundError(resource_type="Dataset", resource_id=DS, message="this upload is tsv")
    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=_user_data()), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=_record()), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock, return_value=pd.DataFrame({"a": [1]})), \
         patch.object(routes, "FixSuggestionEngine", return_value=engine), \
         patch.object(routes, "ensure_metadata_twin", new_callable=AsyncMock, side_effect=refused):
        single = await routes.apply_fix(FixApplicationRequest(dataset_id=DS, issue_id="i1", preview_mode=False), USER)
        engine.apply_batch_fixes = AsyncMock(return_value=(pd.DataFrame({"a": [1]}), [MagicMock(issue_id="i1")], []))
        batch = await routes.batch_apply_fixes(BatchFixRequest(dataset_id=DS, issue_ids=["i1"], preview_mode=False), USER)

    assert (single.success, single.error) == (False, "this upload is tsv")
    assert (batch.success, batch.error) == (False, "this upload is tsv")


async def test_a_batch_preview_lists_each_issues_first_fix_and_moves_nothing():
    safe = MagicMock(fix_id="safe", is_safe=True, estimated_rows_affected=2)
    risky = MagicMock(fix_id="risky", is_safe=False, estimated_rows_affected=5)
    record = MagicMock(issues=[
        MagicMock(issue_id="i1", suggested_fixes=[safe]),
        MagicMock(issue_id="i2", suggested_fixes=[risky]),
        MagicMock(issue_id="i3", suggested_fixes=[]),
    ])

    def preview(safe_only: bool):
        return routes.batch_apply_fixes(BatchFixRequest(
            dataset_id=DS, issue_ids=["i1", "i2", "i3"], preview_mode=True, auto_apply_safe=safe_only), USER)

    with patch.object(routes.UserData, "find_one", new_callable=AsyncMock, return_value=_user_data()), \
         patch.object(routes.DataIssueRecord, "find_one", new_callable=AsyncMock, return_value=record), \
         patch.object(routes, "get_dataframe_from_s3", new_callable=AsyncMock) as download:
        everything, safe_only = await preview(False), await preview(True)

    assert [(r.fix_id, r.affected_rows) for r in everything.results] == [("safe", 2), ("risky", 5)]
    assert [r.fix_id for r in safe_only.results] == ["safe"]
    assert everything.warnings == ["Preview mode - fixes not applied"]
    download.assert_not_called()
