"""#943: erasing a dataset removes the models trained on it, by whichever id it is erased.

Training keys `MLModel.dataset_id` and `TrainingJob.dataset_id` on the upload's
`UserData` id. The cascade swept models and string-keyed children only when a
`DatasetMetadata` parent existed, and only under the id it was called with, so:

- a UI upload (no twin until it is first transformed) kept its models and jobs;
- a `/datasets/upload` pair erased by its metadata id kept them too (they are keyed by
  the other id), and erased by its `UserData` id it kept its metadata twin as well.

The models here are stored the way `train_model_task` stores them. The earlier proof
seeded a model under the id it then erased, which is why it never met this.
"""

import pytest

from app.models.dataset import DatasetMetadata
from app.models.ml_model import MLModel
from app.models.prediction_event import PredictionEvent
from app.models.training_job import TrainingJob
from app.models.user_data import UserData
from app.services.erasure_service import dataset_erasure_service

pytestmark = pytest.mark.asyncio

USER = "erasure_943_user"
BUCKET = dataset_erasure_service.s3_service.bucket_name


@pytest.fixture(autouse=True)
def _no_s3():
    """Mongo is what this file is about; the S3 half is the LocalStack demo's."""
    services = [dataset_erasure_service.s3_service, dataset_erasure_service.model_storage.s3_service]
    saved = [s.is_mock_mode for s in services]
    for s in services:
        s.is_mock_mode = True
    yield
    for s, was in zip(services, saved, strict=True):
        s.is_mock_mode = was


async def _upload(name: str) -> UserData:
    return await UserData(
        user_id=USER, filename=f"{name}.csv", original_filename=f"{name}.csv", file_type="csv",
        s3_url=f"s3://{BUCKET}/datasets/{USER}/{name}.csv", num_rows=3, num_columns=2, data_schema=[],
    ).insert()


async def _twin(upload: UserData, dataset_id: str) -> DatasetMetadata:
    return await DatasetMetadata(
        user_id=USER, dataset_id=dataset_id, filename=upload.filename, original_filename=upload.filename,
        file_type="csv", file_path=upload.s3_url, s3_url=upload.s3_url, num_rows=3, num_columns=2,
    ).insert()


async def _trained_on(upload: UserData, model_id: str) -> None:
    """What a finished training leaves, keyed as `train_model_task` keys it."""
    dataset_id = str(upload.id)
    await TrainingJob(model_id=model_id, user_id=USER, dataset_id=dataset_id, target_column="y").insert()
    await MLModel(
        user_id=USER, dataset_id=dataset_id, model_id=model_id, name="m", problem_type="regression",
        algorithm="Random Forest", target_column="y", feature_names=["a"], cv_score=0.8, test_score=0.8,
        training_time=1.0, model_size=10, n_samples_train=3, n_features=1,
        model_path=f"s3://{BUCKET}/models/{USER}/{model_id}/model.pkl",
    ).insert()
    await PredictionEvent(model_id=model_id, prediction_id=f"p-{model_id}", input_data={"a": 1}).insert()


async def _left() -> dict[str, int]:
    return {
        "uploads": await UserData.find(UserData.user_id == USER).count(),
        "twins": await DatasetMetadata.find(DatasetMetadata.user_id == USER).count(),
        "models": await MLModel.find(MLModel.user_id == USER).count(),
        "jobs": await TrainingJob.find(TrainingJob.user_id == USER).count(),
        "predictions": await PredictionEvent.find({"model_id": {"$regex": "^model_943_"}}).count(),
    }


NOTHING = {"uploads": 0, "twins": 0, "models": 0, "jobs": 0, "predictions": 0}


async def test_a_ui_upload_with_no_twin_takes_its_models_with_it(setup_database):
    upload = await _upload("visits")
    await _trained_on(upload, "model_943_a")

    manifest = await dataset_erasure_service.erase_dataset(str(upload.id), USER)

    assert await _left() == NOTHING
    assert manifest.documents_deleted["ml_models"] == 1
    assert manifest.documents_deleted["training_jobs"] == 1
    assert manifest.failures == []


async def test_a_transformed_upload_whose_twin_shares_its_id(setup_database):
    """The #850 twin: this shape already worked, and has to keep working."""
    upload = await _upload("visits")
    await _twin(upload, str(upload.id))
    await _trained_on(upload, "model_943_b")

    await dataset_erasure_service.erase_dataset(str(upload.id), USER)

    assert await _left() == NOTHING


@pytest.mark.parametrize("erase_by", ["the metadata id", "the upload id"])
async def test_a_pair_with_two_ids_is_erased_whole_by_either(setup_database, erase_by):
    """`/datasets/upload` writes both documents, each under its own id."""
    upload = await _upload("visits")
    await _twin(upload, "dataset_943_pair")
    await _trained_on(upload, "model_943_c")
    target = "dataset_943_pair" if erase_by == "the metadata id" else str(upload.id)

    await dataset_erasure_service.erase_dataset(target, USER)

    assert await _left() == NOTHING


async def test_another_dataset_of_the_same_owner_keeps_its_model(setup_database):
    erased, kept = await _upload("visits"), await _upload("orders")
    await _trained_on(erased, "model_943_d")
    await _trained_on(kept, "model_943_e")

    await dataset_erasure_service.erase_dataset(str(erased.id), USER)

    assert await _left() == {"uploads": 1, "twins": 0, "models": 1, "jobs": 1, "predictions": 1}
    assert (await MLModel.find_one(MLModel.user_id == USER)).model_id == "model_943_e"


async def test_an_id_the_caller_does_not_own_erases_nothing(setup_database):
    upload = await _upload("visits")
    await _trained_on(upload, "model_943_f")

    manifest = await dataset_erasure_service.erase_dataset(str(upload.id), "someone_else")

    assert (await _left())["models"] == 1 and manifest.documents_deleted == {}
