"""#712: a chart reads the columns it draws and filters on, not the whole dataset.

Every chart read the entire file into pandas to use one or two columns of it. A dataset
is Parquet once it has been transformed, and Parquet is stored column by column, so the
others need never be decoded. Real bytes at the seam where each reader downloads; the
reads themselves are watched, not replaced.
"""
import io
import json
from unittest.mock import patch

import pandas as pd
import pytest

from app.models.user_data import UserData
from app.services.s3_service import read_columns_from_bytes

TEST_USER = "test_user_123"
FRAME = pd.DataFrame(
    {
        "visits": [1, 2, 3, 4, 5, 6],
        "spend": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        "region": ["north", "south", "north", "south", "north", "south"],
        "notes": ["a", "b", "c", "d", "e", "f"],
        "day": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06"],
    }
)


def _parquet() -> bytes:
    buffer = io.BytesIO()
    FRAME.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _xlsx() -> bytes:
    buffer = io.BytesIO()
    FRAME.to_excel(buffer, index=False)
    return buffer.getvalue()


STORED_AS = {
    "csv": FRAME.to_csv(index=False).encode(),
    "parquet": _parquet(),
    "xlsx": _xlsx(),
    "json": FRAME.to_json(orient="records").encode(),
}


@pytest.mark.parametrize("kind", sorted(STORED_AS))
def test_the_named_columns_come_back_in_file_order_whatever_the_format(kind):
    frame = read_columns_from_bytes(STORED_AS[kind], {"spend", "visits", "no_such_column"})

    assert list(frame.columns) == ["visits", "spend"]
    assert frame["spend"].tolist() == [10, 20, 30, 40, 50, 60]


def test_a_parquet_file_is_asked_for_those_columns_only():
    with patch("pandas.read_parquet", wraps=pd.read_parquet) as read:
        read_columns_from_bytes(STORED_AS["parquet"], {"spend", "region"})

    assert read.call_args.kwargs["columns"] == ["spend", "region"]


def test_a_csv_is_parsed_with_the_other_columns_skipped():
    with patch("pandas.read_csv", wraps=pd.read_csv) as read:
        frame = read_columns_from_bytes(STORED_AS["csv"], {"spend"})

    keep = read.call_args.kwargs["usecols"]
    assert keep("spend") and not keep("notes")
    assert list(frame.columns) == ["spend"]


class _Stored:
    """The dataset's bytes at the download seam, and which columns each read asked for."""

    def __init__(self, monkeypatch, module, content: bytes):
        self.asked: list[list[str] | None] = []
        monkeypatch.setattr(module, "get_file_from_s3", lambda _url: io.BytesIO(content))
        real = pd.read_parquet

        def watched(*args, **kwargs):
            self.asked.append(kwargs.get("columns"))
            return real(*args, **kwargs)

        monkeypatch.setattr(pd, "read_parquet", watched)


async def _dataset() -> UserData:
    doc = UserData(
        user_id=TEST_USER, filename="visits.parquet", original_filename="visits.csv",
        file_path=f"transformed/{TEST_USER}/visits.parquet",
        s3_url=f"s3://test-bucket/transformed/{TEST_USER}/visits.parquet",
        num_rows=6, num_columns=5, data_schema=[], file_type="parquet",
    )
    await doc.insert()
    return doc


@pytest.mark.asyncio
async def test_a_scatter_plot_reads_its_two_columns_and_the_one_it_filters_on(
    setup_database, async_authorized_client, monkeypatch
):
    from app.api.routes import visualizations

    doc = await _dataset()
    stored = _Stored(monkeypatch, visualizations, STORED_AS["parquet"])
    filters = json.dumps([{"column": "region", "operator": "equals", "value": "north"}])

    response = await async_authorized_client.get(
        f"/api/v1/visualizations/scatter/{doc.id}/visits/spend", params={"filters": filters}
    )

    body = response.json()
    assert response.status_code == 200, response.text
    assert stored.asked == [["visits", "spend", "region"]]
    assert body["data"] == [{"x": 1.0, "y": 10.0}, {"x": 3.0, "y": 30.0}, {"x": 5.0, "y": 50.0}]
    assert body["total_rows"] == 3 and body["correlation"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_a_line_chart_and_a_time_series_read_only_what_they_draw(
    setup_database, async_authorized_client, monkeypatch
):
    from app.api.routes import visualizations

    doc = await _dataset()
    stored = _Stored(monkeypatch, visualizations, STORED_AS["parquet"])

    line = await async_authorized_client.get(
        f"/api/v1/visualizations/line/{doc.id}/visits", params={"y_columns": "spend,not_a_column"}
    )
    series = await async_authorized_client.get(f"/api/v1/visualizations/timeseries/{doc.id}/day/spend")

    assert line.status_code == 200, line.text
    assert series.status_code == 200, series.text
    assert stored.asked == [["visits", "spend"], ["spend", "day"]]
    assert line.json()["data"][0] == {"x": 1, "spend": 10.0}
    assert line.json()["lines"] == [{"dataKey": "spend", "label": "spend"}]
    assert series.json()["timestamps"][0] == "2026-01-01 00:00:00" and series.json()["values"][-1] == 60.0
    assert series.json()["total_rows"] == 6


@pytest.mark.asyncio
async def test_a_histogram_and_a_box_plot_read_their_one_column(setup_database, async_authorized_client, monkeypatch):
    from app.services import visualization_cache

    doc = await _dataset()
    stored = _Stored(monkeypatch, visualization_cache, STORED_AS["parquet"])

    histogram = await async_authorized_client.get(f"/api/v1/visualizations/histogram/{doc.id}/visits")
    boxplot = await async_authorized_client.get(f"/api/v1/visualizations/boxplot/{doc.id}/spend")
    correlation = await async_authorized_client.get(f"/api/v1/visualizations/correlation/{doc.id}")

    assert histogram.status_code == 200 and boxplot.status_code == 200 and correlation.status_code == 200
    assert boxplot.json()["median"] == 35.0
    # the correlation matrix is of every numeric column, so it reads the file whole
    assert stored.asked == [["visits"], ["spend"], None]


@pytest.mark.asyncio
async def test_a_filter_that_is_not_json_is_refused_before_anything_is_read(
    setup_database, async_authorized_client, monkeypatch
):
    from app.api.routes import visualizations

    doc = await _dataset()
    stored = _Stored(monkeypatch, visualizations, STORED_AS["parquet"])

    response = await async_authorized_client.get(
        f"/api/v1/visualizations/scatter/{doc.id}/visits/spend", params={"filters": "{not json"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid filter format"
    assert stored.asked == []


@pytest.mark.parametrize(
    "value, sent",
    [(3, 3), (2.5, 2.5), ("north", "north"), (True, "True"), (None, None), (float("nan"), None), (pd.Timestamp("2026-01-02"), "2026-01-02 00:00:00")],
)
def test_a_line_charts_x_is_sent_as_what_it_is(value, sent):
    """A numeric x used to arrive as text, so the axis treated numbers as labels."""
    from app.api.routes.visualizations import _native_x

    assert _native_x(value) == sent and type(_native_x(value)) is type(sent)


CHARTS = [
    ("scatter", "visits/spend", {}),
    ("line", "visits", {"y_columns": "spend"}),
    ("timeseries", "day/spend", {}),
]


@pytest.mark.parametrize("kind, path, params", CHARTS, ids=[c[0] for c in CHARTS])
@pytest.mark.asyncio
async def test_each_chart_refuses_what_it_refused_before(
    setup_database, async_authorized_client, monkeypatch, kind, path, params
):
    """The three routes share one flow now; each keeps its own answers."""
    from app.api.routes import visualizations

    doc = await _dataset()
    theirs = await _dataset()
    await theirs.set({UserData.user_id: "someone-else"})
    stored = _Stored(monkeypatch, visualizations, STORED_AS["parquet"])
    url = f"/api/v1/visualizations/{kind}/{{id}}/{path}"

    bad_filter = await async_authorized_client.get(url.format(id=doc.id), params={**params, "filters": "{not json"})
    foreign = await async_authorized_client.get(url.format(id=theirs.id), params=params)
    assert bad_filter.status_code == 400 and bad_filter.json()["detail"] == "Invalid filter format"
    assert foreign.status_code == 404 and foreign.json()["detail"] == "Dataset not found"
    assert stored.asked == []

    def unreadable(_url):
        raise RuntimeError("s3://test-bucket/transformed/secret.parquet is gone")

    monkeypatch.setattr(visualizations, "get_file_from_s3", unreadable)
    failed = await async_authorized_client.get(url.format(id=doc.id), params=params)
    assert failed.status_code == 500
    assert "secret.parquet" not in failed.text


@pytest.mark.asyncio
async def test_a_chart_already_computed_is_served_without_reading_the_file(
    setup_database, async_authorized_client, monkeypatch
):
    from app.api.routes import visualizations

    doc = await _dataset()
    stored = _Stored(monkeypatch, visualizations, STORED_AS["parquet"])
    kept: dict = {}

    async def get(key):
        return kept.get(key)

    async def put(key, value, ttl=None):
        kept[key] = value

    # Through the shared cache's own dict, which is cleaned up on undo (tasks/lessons.md, #683).
    monkeypatch.setitem(vars(visualizations.cache_service), "get", get)
    monkeypatch.setitem(vars(visualizations.cache_service), "set", put)
    url = f"/api/v1/visualizations/scatter/{doc.id}/visits/spend"

    first = await async_authorized_client.get(url)
    second = await async_authorized_client.get(url)

    assert first.status_code == 200 and second.json() == first.json()
    assert stored.asked == [["visits", "spend"]]  # one read for two requests
    assert list(kept)[0].startswith(f"viz:{doc.id}:scatter:")
