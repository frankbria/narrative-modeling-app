"""#694: the backend names its database once, and refuses a URI that names another.

The backend selects `client[MONGODB_DB]` and never reads a database in the URI's
path. So `MONGODB_URI=…/narrative_prod` with `MONGODB_DB=narrative_staging` ran against
staging while the URI said production, and could disagree with the frontend, which has
refused that since #551.
"""
import pytest

from app.config import database_name_in_uri, resolve_database_name


@pytest.mark.parametrize(
    "uri, named",
    [
        ("mongodb://localhost:27017", None),
        ("mongodb://localhost:27017/", None),
        ("mongodb://localhost:27017/narrative_test", "narrative_test"),
        ("mongodb://u:p@h1:27017,h2:27017/app_db?replicaSet=rs0", "app_db"),
        ("mongodb+srv://u:p@cluster.example.net/?retryWrites=true&w=majority", None),
        ("mongodb+srv://u:p@cluster.example.net/narrative_modeling-staging?retryWrites=true", "narrative_modeling-staging"),
        ("MONGODB+SRV://u:p@cluster.example.net/Mixed", "Mixed"),
        ("", None),
        (None, None),
    ],
)
def test_the_database_a_uri_names_in_its_path(uri, named):
    assert database_name_in_uri(uri) == named


def test_the_configured_name_is_used_when_the_uri_names_none_or_the_same():
    assert resolve_database_name("mongodb://localhost:27017", "narrative_test") == "narrative_test"
    assert resolve_database_name("mongodb://localhost:27017/narrative_test", "narrative_test") == "narrative_test"
    assert resolve_database_name(None, "narrative_test") == "narrative_test"


@pytest.mark.parametrize("unset", [None, "", "   "])
def test_no_configured_name_is_refused(unset):
    with pytest.raises(RuntimeError, match="MONGODB_DB environment variable is not set"):
        resolve_database_name("mongodb://localhost:27017/narrative_test", unset)


def test_a_uri_that_names_a_different_database_is_refused_without_its_credentials():
    uri = "mongodb+srv://app_user:s3cret@cluster.example.net/narrative_prod?retryWrites=true"

    with pytest.raises(RuntimeError) as refused:
        resolve_database_name(uri, "narrative_staging")

    message = str(refused.value)
    assert "narrative_staging" in message and "narrative_prod" in message
    assert "s3cret" not in message and "app_user" not in message and "cluster.example.net" not in message


@pytest.mark.asyncio
async def test_the_app_does_not_start_against_a_database_the_uri_does_not_name(monkeypatch):
    from asgi_lifespan import LifespanManager

    from app.main import app

    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/narrative_modeling_elsewhere")
    monkeypatch.setenv("MONGODB_DB", "narrative_modeling_test")

    with pytest.raises(RuntimeError, match="name different databases"):
        async with LifespanManager(app):
            pass
