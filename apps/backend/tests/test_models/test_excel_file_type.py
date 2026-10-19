"""#902: an Excel dataset is stored under its extension, by every writer.

`/upload/secure`, `/upload/confirm-pii-upload` and chunked `complete` stored `"excel"`;
`/upload/` and `/datasets/upload` stored `"xls"` or `"xlsx"`. Readers disagreed about
which they accept, so an Excel file uploaded through the UI failed at whichever stage
met a reader that knew only the extensions. The models now hold one spelling: the
extension, which is what `record_new_file` and the audit script already go by.
"""
import io

import pandas as pd
import pytest

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

pytestmark = pytest.mark.asyncio


def _upload(file_type: str | None, name: str, url: str | None = None) -> UserData:
    return UserData(
        user_id="u", filename=name, original_filename=name, file_type=file_type,
        s3_url=url or f"s3://b/datasets/u/0b0f6c1e.{name.rsplit('.', 1)[-1]}",
        num_rows=1, num_columns=1, data_schema=[],
    )


@pytest.mark.parametrize("name, stored", [
    ("q3 sales.xlsx", "xlsx"),
    ("LEDGER.XLS", "xls"),
])
async def test_an_upload_typed_excel_is_stored_under_its_extension(setup_database, name, stored):
    doc = await _upload("excel", name).insert()

    assert doc.file_type == stored
    raw = await UserData.get_motor_collection().find_one({"_id": doc.id})
    assert raw["file_type"] == stored, "what is in the database, not only what the model shows"


async def test_the_objects_name_decides_when_the_filename_does_not_say(setup_database):
    """/upload/secure can type a file excel from its content type alone."""
    doc = _upload("excel", "export", url="s3://b/datasets/u/0b0f6c1e.xls")

    assert doc.file_type == "xls"


async def test_excel_with_no_extension_anywhere_is_a_workbook(setup_database):
    assert _upload("excel", "export", url="s3://b/datasets/u/blob").file_type == "xlsx"


@pytest.mark.parametrize("file_type", ["csv", "xlsx", "xls", "parquet", "json", None])
async def test_every_other_type_is_left_as_it_is(setup_database, file_type):
    assert _upload(file_type, "d.csv").file_type == file_type


async def test_a_row_stored_as_excel_reads_back_under_its_extension(setup_database):
    """Rows written before this change. Every reader that goes through the model sees
    the extension, so none has to know the old spelling."""
    doc = await _upload("xlsx", "q3.xlsx").insert()
    await UserData.get_motor_collection().update_one({"_id": doc.id}, {"$set": {"file_type": "excel"}})

    assert (await UserData.get(doc.id)).file_type == "xlsx"


async def test_the_metadata_twin_holds_the_same_spelling(setup_database):
    meta = DatasetMetadata(
        user_id="u", dataset_id="d1", filename="q3.xlsx", original_filename="q3.xlsx", file_type="excel",
        file_path="datasets/u/q3.xlsx", s3_url="s3://b/datasets/u/q3.xlsx", num_rows=1, num_columns=1,
    )

    assert meta.file_type == "xlsx"


def _workbook() -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame({"id": [1, 2], "color": ["red", "blue"]}).to_excel(buffer, index=False)
    return buffer.getvalue()


class TestReadersOfARowStoredAsExcel:
    """A real workbook and a row whose stored type is the old spelling, through each
    reader that dispatches on `file_type`."""

    async def _stored_as_excel(self) -> UserData:
        doc = await _upload("xlsx", "colors.xlsx").insert()
        await UserData.get_motor_collection().update_one({"_id": doc.id}, {"$set": {"file_type": "excel"}})
        return await UserData.get(doc.id)

    async def test_training(self, setup_database):
        from app.api.routes.model_training import _parse_and_hash

        row = await self._stored_as_excel()

        assert list(_parse_and_hash(_workbook(), row.file_type)[0].columns) == ["id", "color"]

    async def test_the_shared_loader(self, setup_database, tmp_path):
        """the transformation engine and EDA read through it."""
        from app.services.s3_service import _read_dataframe

        row = await self._stored_as_excel()
        path = tmp_path / "object"
        path.write_bytes(_workbook())

        assert list(_read_dataframe(str(path), row.file_type, None).columns) == ["id", "color"]

    async def test_data_processing(self, setup_database):
        """The explore page's reader, which knows a workbook as "excel"."""
        from app.services.data_processing.data_processor import DataProcessor

        row = await self._stored_as_excel()

        processed = await DataProcessor().process_bytes(_workbook(), row.original_filename, file_type=row.file_type)

        assert list(processed.dataframe.columns) == ["id", "color"]
