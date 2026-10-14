"""#852: which version a transformation's result is recorded as derived from.

It was always the dataset's latest version by number. That is the frame being
transformed only while a dataset moves forward: after an undo the latest is the
version that was undone. The route-level flow (apply, apply, undo, apply, against real
S3) is in tests/test_integration/test_lineage_after_undo_localstack.py; these hold the
choice itself, on real documents.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.transformation import TransformationConfig, TransformationStep
from app.models.version import DatasetVersion
from app.services.transformation_service import TransformationService

pytestmark = pytest.mark.asyncio

USER = "u852"
DATASET = SimpleNamespace(dataset_id="d852")
CONFIG = "config_852"


async def _version(version_id: str, number: int, user_id: str = USER, dataset_id: str = "d852") -> None:
    await DatasetVersion(
        version_id=version_id, dataset_id=dataset_id, version_number=number, user_id=user_id,
        content_hash=f"hash-{version_id}", file_size=1, file_path=f"versions/{user_id}/{version_id}/data.parquet",
        s3_url=f"s3://bucket/versions/{user_id}/{version_id}/data.parquet", num_rows=1, num_columns=1,
        schema_hash="schema", created_by=user_id,
    ).insert()


async def _history(position: int, steps: list[str | None], base: str | None = None) -> None:
    await TransformationConfig(
        user_id=USER, dataset_id="d852", config_id=CONFIG, current_position=position, base_version_id=base,
        transformation_steps=[TransformationStep(transformation_type="trim_whitespace", version_id=v) for v in steps],
    ).insert()


async def _parent(derived_from: str | None = None) -> str:
    service = TransformationService()
    known = await service._known_parent(derived_from, CONFIG)
    return (await service._parent_version(DatasetVersion, DATASET, USER, known)).version_id


@pytest.fixture
async def three_versions(setup_database):
    await _version("v_upload", 1)
    await _version("v_first", 2)
    await _version("v_second", 3)


async def test_after_an_undo_it_is_the_step_the_dataset_is_at_not_the_latest(three_versions):
    await _history(position=0, steps=["v_first", "v_second"])

    assert await _parent() == "v_first"


async def test_with_every_step_undone_it_is_the_base(three_versions):
    await _history(position=-1, steps=["v_first", "v_second"], base="v_upload")

    assert await _parent() == "v_upload"


async def test_a_later_step_of_one_apply_derives_from_the_step_before_it(three_versions):
    # The cursor has not moved yet: it still says v_first.
    await _history(position=0, steps=["v_first"])

    assert await _parent(derived_from="v_second") == "v_second"


@pytest.mark.parametrize(
    ("position", "steps"),
    [(-1, []), (0, [None])],
    ids=["a history with no step and no base", "a step whose version was never written"],
)
async def test_when_the_history_does_not_know_it_is_the_latest(three_versions, position, steps):
    await _history(position=position, steps=steps)

    assert await _parent() == "v_second"


async def test_with_no_history_at_all_it_is_the_latest(three_versions):
    assert await _parent() == "v_second"


async def test_a_version_of_another_dataset_or_another_tenant_is_never_the_parent(three_versions):
    """The cursor's id is looked up under the caller's own dataset, so a history that
    named a foreign version falls back to the caller's latest."""
    await _version("v_theirs", 9, user_id="someone_else")
    await _version("v_other_dataset", 9, dataset_id="another")

    for foreign in ("v_theirs", "v_other_dataset"):
        assert await _parent(derived_from=foreign) == "v_second"


async def test_a_step_whose_version_was_not_written_is_passed_over_not_derived_from():
    """Writing a version is best-effort. In a three-step apply whose second version
    fails, the third derives from the first: the last one this apply actually wrote."""
    service = TransformationService()
    wrote = iter(["v_first", None, "v_third"])
    derived_from: list[str | None] = []

    async def versioned(_dataset, _dataset_id, _user_id, _step, _done, parent=None):
        derived_from.append(parent)
        return {"version_id": next(wrote)}

    steps = iter([SimpleNamespace(after=n) for n in range(3)])
    with (
        patch.object(service, "_versioned", versioned),
        patch.object(service, "_history_config_id", AsyncMock(return_value=CONFIG)),
        patch.object(service, "_remember_the_start", AsyncMock()),
    ):
        await service._write_versions(SimpleNamespace(s3_url="s3://b/k"), "d852", USER, steps, {}, 0.0)

    assert derived_from == [None, "v_first", "v_first"]
