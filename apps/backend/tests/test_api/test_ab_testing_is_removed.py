"""A/B testing is not offered (#502).

The feature had nine routes and three pages, and nothing in the prediction path ever
assigned a variant or recorded an outcome: an experiment could be created and started
and would collect nothing. The owner's decision was to remove it and keep the models.
Bringing it back means mounting a router again, which this test will meet first.
"""

from app.main import app


def test_the_published_api_has_no_ab_testing_route() -> None:
    paths = list(app.openapi()["paths"])

    assert len(paths) > 100, "the route table is too small to mean anything"
    assert [path for path in paths if "ab-testing" in path or "/experiments" in path] == []
