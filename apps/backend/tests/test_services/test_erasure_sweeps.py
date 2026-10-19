"""Unit tests for the user-erasure sweeps and the retired-collection sweep (#1088).

The collaborators are in-memory fakes, so every branch runs without a database; the real
Mongo and the real cascade are covered by tests/test_integration/test_erase_retired_collections.py
and test_erase_user_account_scoped.py.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.erasure import DeletionManifest
from app.services import erasure_service
from app.services.erasure_service import DatasetErasureService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _manifest() -> DeletionManifest:
    return DeletionManifest(target_type="user", target_id="u", subject_user_id="u")


def _service(*, mock_s3: bool = True) -> DatasetErasureService:
    service = DatasetErasureService.__new__(DatasetErasureService)
    service.model_storage = SimpleNamespace(
        delete_model=AsyncMock(), s3_service=SimpleNamespace(is_mock_mode=mock_s3)
    )
    service._delete_many = AsyncMock()  # type: ignore[method-assign]
    return service


class _Rows:
    """The slice of a Mongo collection the retired sweep uses."""

    def __init__(self, rows=(), fail=False):
        self.rows, self.fail, self.calls = list(rows), fail, []

    def find(self, query, projection=None):
        self.calls.append(("find", query))

        async def gen():
            if self.fail:
                raise RuntimeError("mongo down")
            for row in self.rows:
                yield row

        return gen()

    async def delete_many(self, query):
        self.calls.append(("delete_many", query))
        if self.fail:
            raise RuntimeError("mongo down")
        return SimpleNamespace(deleted_count=len(self.rows))

    async def update_many(self, query, update):
        self.calls.append(("update_many", query, update))
        if self.fail:
            raise RuntimeError("mongo down")
        return SimpleNamespace(modified_count=len(self.rows))


def _retired(monkeypatch, **collections):
    monkeypatch.setattr(
        DatasetErasureService, "_retired", staticmethod(lambda name: collections.setdefault(name, _Rows()))
    )


async def test_leftover_models_are_erased_one_by_one(monkeypatch):
    service, manifest = _service(mock_s3=False), _manifest()
    service.model_storage.delete_model.side_effect = [None, RuntimeError("s3 down")]
    models = [SimpleNamespace(model_id="m1"), SimpleNamespace(model_id="m2")]
    find = MagicMock(return_value=SimpleNamespace(to_list=AsyncMock(return_value=models)))
    monkeypatch.setattr(erasure_service, "MLModel", SimpleNamespace(find=find, user_id="user_id"))

    await service._erase_leftover_models("u", manifest)

    assert manifest.documents_deleted == {"ml_models": 1}
    assert manifest.s3_objects_deleted == ["models/u/m1/"]
    assert [f.split(":")[0] for f in manifest.failures] == ["delete_model m2"]
    # a failed model's prediction log is still erased
    assert [c.args[1] for c in service._delete_many.await_args_list] == [{"model_id": "m1"}, {"model_id": "m2"}]


async def test_a_mock_bucket_records_no_s3_key(monkeypatch):
    service, manifest = _service(mock_s3=True), _manifest()

    await service._erase_leftover_model(SimpleNamespace(model_id="m1"), "u", manifest)

    assert manifest.documents_deleted == {"ml_models": 1} and manifest.s3_objects_deleted == []


async def test_a_failed_model_query_is_recorded(monkeypatch):
    service, manifest = _service(), _manifest()
    find = MagicMock(return_value=SimpleNamespace(to_list=AsyncMock(side_effect=RuntimeError("down"))))
    monkeypatch.setattr(erasure_service, "MLModel", SimpleNamespace(find=find, user_id="user_id"))

    await service._erase_leftover_models("u", manifest)

    assert manifest.failures == ["query ml_models: down"]


@pytest.mark.parametrize("modified, notes", [(2, 1), (0, 0)])
async def test_shared_recipes_are_anonymised_only_when_some_exist(modified, notes):
    manifest = _manifest()
    shared = MagicMock()
    shared.find.return_value.update = AsyncMock(return_value=SimpleNamespace(modified_count=modified))
    with patch("app.services.transformation_engine.recipe_manager.SharedRecipe", shared):
        await _service()._anonymize_shared_recipes("u", manifest)

    assert len(manifest.notes) == notes and manifest.failures == []


async def test_a_failed_anonymisation_is_recorded():
    manifest = _manifest()
    shared = MagicMock()
    shared.find.return_value.update = AsyncMock(side_effect=RuntimeError("down"))
    with patch("app.services.transformation_engine.recipe_manager.SharedRecipe", shared):
        await _service()._anonymize_shared_recipes("u", manifest)

    assert manifest.failures == ["anonymize shared_recipes: down"]


@pytest.mark.parametrize("count, notes, failures", [(3, 1, 0), (0, 0, 0), (None, 0, 1)])
async def test_billing_retention_is_noted_when_there_is_billing_state(count, notes, failures):
    manifest = _manifest()
    counter = MagicMock()
    counter.find.return_value.count = (
        AsyncMock(return_value=count) if count is not None else AsyncMock(side_effect=RuntimeError("down"))
    )
    with patch("app.models.subscription.Subscription", counter), patch("app.models.usage.UsageRecord", counter):
        await _service()._note_billing_retention("u", manifest)

    assert (len(manifest.notes), len(manifest.failures)) == (notes, failures)


async def test_the_user_sweep_visits_every_collection_and_both_dataset_cascades():
    service, manifest = _service(), _manifest()
    for name in (
        "_erase_leftover_models", "_erase_batch_jobs", "_erase_version_artifacts",
        "_anonymize_shared_recipes", "_sweep_retired_user_scoped", "_note_billing_retention",
    ):
        setattr(service, name, AsyncMock())

    await service._sweep_user_scoped("u", manifest)

    swept = {c.args[0].__name__ for c in service._delete_many.await_args_list}
    assert {"APIKey", "TransformationRecipe", "SharedRecipe", "DatasetVersion", "TrainingJob"} <= swept
    service._erase_version_artifacts.assert_awaited_once_with({"user_id": "u"}, manifest)
    service._sweep_retired_user_scoped.assert_awaited_once_with("u", manifest)
    service._note_billing_retention.assert_awaited_once_with("u", manifest)


async def test_the_retired_sweep_deletes_by_owner_and_pulls_from_acls(monkeypatch):
    service, manifest = DatasetErasureService.__new__(DatasetErasureService), _manifest()
    collections = {
        name: _Rows([{"feature_id": "f1"}])
        for name in ("data_issues", "feature_definitions", "feature_store", "feature_versions", "feature_collections")
    }
    _retired(monkeypatch, **collections)

    await service._sweep_retired_user_scoped("u", manifest)

    assert ("delete_many", {"feature_id": {"$in": ["f1"]}}) in collections["feature_versions"].calls
    for name in ("data_issues", "feature_definitions", "feature_store", "feature_collections"):
        assert ("delete_many", {"user_id": "u"}) in collections[name].calls
    assert sum("shared_with" in n for n in manifest.notes) == 2
    assert manifest.documents_deleted["feature_versions"] == 1 and manifest.failures == []


async def test_retired_failures_are_recorded_not_raised(monkeypatch):
    service, manifest = DatasetErasureService.__new__(DatasetErasureService), _manifest()
    broken = _Rows([{"feature_id": "f1"}], fail=True)
    _retired(monkeypatch, data_issues=broken, feature_store=broken, feature_versions=broken, feature_collections=broken)

    await service._sweep_retired_user_scoped("u", manifest)

    prefixes = {f.split(":")[0] for f in manifest.failures}
    assert {"sweep feature_versions", "delete data_issues", "scrub shared_with feature_store"} <= prefixes
