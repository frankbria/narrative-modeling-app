"""#996: a chart filter list of the wrong shape is the caller's 400, naming the entry.

Only malformed JSON was refused. An entry missing a key, a column the dataset lacks or
`contains` on a number reached the generic handler and answered a 500, and an unknown
operator was skipped, so the chart came back unfiltered. Real dataset documents; the
download seam serves the stored bytes and records what was read.
"""

import json

import pytest

from tests.test_services.test_charts_read_only_their_columns import (
    STORED_AS,
    _dataset,
    _Stored,
)

pytestmark = pytest.mark.asyncio


async def _scatter(client, monkeypatch, filters, *, columns: list[str] | None = None):
    from app.api.routes import visualizations

    doc = await _dataset()
    if columns is not None:
        await doc.set({"columns": columns})
    stored = _Stored(monkeypatch, visualizations, STORED_AS["parquet"])
    response = await client.get(
        f"/api/v1/visualizations/scatter/{doc.id}/visits/spend",
        params={"filters": filters if isinstance(filters, str) else json.dumps(filters)},
    )
    return response, stored.asked


@pytest.mark.parametrize(
    "filters, detail",
    [
        ({"column": "region", "operator": "equals", "value": "north"}, "Invalid filter format: expected a list of filters"),
        ([{"column": "region", "value": "north"}], "Filter 1: each filter needs a column, an operator and a value"),
        (["region"], "Filter 1: each filter needs a column, an operator and a value"),
        ([{"column": "region", "operator": "equals", "value": "north"},
          {"column": "spend", "operator": "at_least", "value": 5}], "Filter 2: unknown operator 'at_least'"),
        ([{"column": "spend", "operator": "between", "value": 5}], "Filter 1: between takes a list of two values"),
        ([{"column": "region", "operator": ["equals"], "value": "north"}], "Filter 1: the column and the operator are names"),
        ([{"column": ["region"], "operator": "equals", "value": "north"}], "Filter 1: the column and the operator are names"),
    ],
    ids=[
        "not a list", "a missing key", "not an object", "an unknown operator", "between without a pair",
        "an operator that is not a name", "a column that is not a name",
    ],
)
async def test_a_filter_of_the_wrong_shape_is_refused_before_anything_is_read(
    setup_database, async_authorized_client, monkeypatch, filters, detail
):
    response, asked = await _scatter(async_authorized_client, monkeypatch, filters)

    assert (response.status_code, response.json()["detail"]) == (400, detail)
    assert asked == []


async def test_a_column_the_dataset_records_it_lacks_is_refused_before_the_download(
    setup_database, async_authorized_client, monkeypatch
):
    filters = [{"column": "postcode", "operator": "equals", "value": "N1"}]

    response, asked = await _scatter(
        async_authorized_client, monkeypatch, filters, columns=["visits", "spend", "region", "notes", "day"]
    )

    assert (response.status_code, response.json()["detail"]) == (400, "Filter 1: the dataset has no column 'postcode'")
    assert asked == []


async def test_a_column_the_file_lacks_is_refused_when_no_columns_are_recorded(
    setup_database, async_authorized_client, monkeypatch
):
    filters = [{"column": "postcode", "operator": "equals", "value": "N1"}]

    response, _ = await _scatter(async_authorized_client, monkeypatch, filters)

    assert (response.status_code, response.json()["detail"]) == (400, "Filter 1: the dataset has no column 'postcode'")


@pytest.mark.parametrize(
    "entry",
    [
        {"column": "visits", "operator": "contains", "value": "1"},
        {"column": "visits", "operator": "greater_than", "value": "many"},
    ],
    ids=["contains on numbers", "greater_than text against numbers"],
)
async def test_an_operator_that_does_not_apply_to_the_columns_values_is_a_400(
    setup_database, async_authorized_client, monkeypatch, entry
):
    response, _ = await _scatter(async_authorized_client, monkeypatch, [entry])

    assert response.status_code == 400
    assert response.json()["detail"] == f"Filter 1: {entry['operator']} does not apply to the values of 'visits'"


async def test_every_operator_still_filters(setup_database, async_authorized_client, monkeypatch):
    filters = [
        {"column": "region", "operator": "contains", "value": "nor"},
        {"column": "visits", "operator": "between", "value": [2, 5]},
        {"column": "spend", "operator": "greater_than", "value": 20},
        {"column": "spend", "operator": "less_than", "value": 60},
        {"column": "notes", "operator": "equals", "value": "c"},
    ]

    response, _ = await _scatter(async_authorized_client, monkeypatch, filters)

    assert response.status_code == 200, response.text
    assert response.json()["data"] == [{"x": 3.0, "y": 30.0}]


@pytest.mark.parametrize("typed, matches", [("(", []), (".", [])], ids=["a bracket", "a dot"])
async def test_contains_matches_what_was_typed_not_a_pattern(
    setup_database, async_authorized_client, monkeypatch, typed, matches
):
    """A regex made "(" a 500 and "." a match for every row."""
    response, _ = await _scatter(
        async_authorized_client, monkeypatch, [{"column": "notes", "operator": "contains", "value": typed}]
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == matches
