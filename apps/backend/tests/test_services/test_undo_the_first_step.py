"""#962: the pieces that let the first step of a history be undone.

The route-level flow (upload, one step, undo, redo, against real S3) is in
tests/test_integration/test_undo_the_first_step_localstack.py. These hold the decisions
that flow depends on: when the starting version is recorded, and what undo does with it.
"""

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.transformation import TransformationConfig
from app.services.exceptions import ValidationError
from app.services.history_service import HistoryService, _cannot_undo
from app.services.transformation_service import TransformationService


@contextlib.asynccontextmanager
async def _no_lease(*_args, **_kwargs):
    yield


@pytest.fixture(autouse=True)
def _no_database_so_no_lease():
    """No database here, so no lease either (#1022)."""
    with patch("app.services.history_service.holding_the_dataset", _no_lease):
        yield

pytestmark = pytest.mark.asyncio

UPLOAD = SimpleNamespace(source_s3_url=None)  # never moved off the file it was uploaded as
MOVED = SimpleNamespace(source_s3_url="s3://bucket/datasets/u/original.csv")


async def _fresh_history(**fields) -> TransformationConfig:
    return await TransformationConfig(user_id="u", dataset_id="d962", config_id="config_962", **fields).insert()


async def _base() -> str | None:
    return (await TransformationConfig.find_one(TransformationConfig.config_id == "config_962")).base_version_id


def _versions(parent: str | None = "v_upload", parent_is_the_upload: bool = True):
    """The step's version, whose parent is `parent`; and that parent."""
    stored = {
        "v_step": SimpleNamespace(parent_version_id=parent),
        parent: SimpleNamespace(parent_version_id=None, is_base_version=parent_is_the_upload),
    }

    async def get_version(version_id, **_kwargs):
        return stored.get(version_id)

    return patch("app.services.versioning_service.versioning_service.get_version", get_version)


class TestTheStartIsRecordedOnlyWhenItIsCertain:
    async def test_the_first_step_of_an_upload_that_never_moved(self, setup_database):
        await _fresh_history()

        with _versions():
            await TransformationService()._remember_the_start("config_962", UPLOAD, "v_step")

        assert await _base() == "v_upload"

    async def test_a_dataset_already_moved_by_an_edit_no_step_describes(self, setup_database):
        """Its latest version is not the file being transformed, so there is no answer."""
        await _fresh_history()

        with _versions():
            await TransformationService()._remember_the_start("config_962", MOVED, "v_step")

        assert await _base() is None

    async def test_a_parent_that_is_not_the_upload_is_not_taken_for_it(self, setup_database):
        """An apply that failed part-way leaves its step's version behind as the latest,
        and a retry with a different transformation derives from that (GLM review)."""
        await _fresh_history()

        with _versions(parent="v_left_behind", parent_is_the_upload=False):
            await TransformationService()._remember_the_start("config_962", UPLOAD, "v_step")

        assert await _base() is None

    async def test_a_history_undone_to_its_start_keeps_the_base_it_has(self, setup_database):
        await _fresh_history(base_version_id="v_upload")

        with _versions(parent="v_something_newer"):
            await TransformationService()._remember_the_start("config_962", UPLOAD, "v_step")

        assert await _base() == "v_upload"

    async def test_a_step_with_no_version_or_no_parent_records_nothing(self, setup_database):
        await _fresh_history()

        with _versions(parent=None):
            await TransformationService()._remember_the_start("config_962", UPLOAD, "v_step")
            await TransformationService()._remember_the_start("config_962", UPLOAD, None)

        assert await _base() is None

    async def test_failing_to_record_it_does_not_fail_the_transformation(self, setup_database):
        await _fresh_history()
        lookup = patch(
            "app.services.versioning_service.versioning_service.get_version",
            AsyncMock(side_effect=RuntimeError("mongo is away")),
        )

        with lookup:
            await TransformationService()._remember_the_start("config_962", UPLOAD, "v_step")

        assert await _base() is None


def _config(position: int, base: str | None, floor: int = 0) -> MagicMock:
    config = MagicMock(current_position=position, base_version_id=base, undo_floor=floor)
    config.transformation_steps = [MagicMock(version_id="v_step")]
    config.can_undo = MagicMock(return_value=base is not None and position == 0 and floor == 0)
    config.save = AsyncMock()
    return config


class TestUndoAtTheFirstStep:
    async def test_it_restores_the_version_from_before_the_step(self):
        config = _config(position=0, base="v_upload")
        service = HistoryService(MagicMock(), MagicMock(get_dataset_config=AsyncMock(return_value=config)))

        with (
            patch("app.services.history_service.history_key", AsyncMock(return_value="d962")),
            patch.object(service, "_move_to_step", AsyncMock()) as move,
        ):
            result = await service.undo("d962", "u")

        move.assert_awaited_once_with("d962", "u", "v_upload")
        assert (result["current_position"], result["version_id"]) == (-1, "v_upload")
        assert "before its first step" in result["message"]
        config.save.assert_awaited_once()

    @pytest.mark.parametrize(
        "position,base,floor,said",
        [
            (-1, "v_upload", 0, "already at the beginning of history"),
            (0, None, 0, "the data from before this step was not saved"),
            (0, "v_upload", 1, "not in this history"),
            (2, "v_upload", 3, "not in this history"),
        ],
    )
    async def test_a_refusal_says_which_of_the_three_reasons_it_is(self, position, base, floor, said):
        assert said in _cannot_undo(_config(position, base, floor))

    async def test_without_a_base_the_first_step_is_refused_as_before(self):
        config = _config(position=0, base=None)
        service = HistoryService(MagicMock(), MagicMock(get_dataset_config=AsyncMock(return_value=config)))

        with patch("app.services.history_service.history_key", AsyncMock(return_value="d962")):
            with pytest.raises(ValidationError, match="beginning of history"):
                await service.undo("d962", "u")
