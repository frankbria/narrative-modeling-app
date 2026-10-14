"""#985: a 403 is never the answer to "this id is someone else's".

Unknown and foreign ids answer alike everywhere (#751 did it for datasets): a 403 for a
foreign one tells any signed-in caller which ids exist. A 403 is right only where the
caller may already know the object exists. These hold that by construction: a route
answers 403 only by mapping `PermissionDeniedError` or from an allow-listed check, and a
service raises `PermissionDeniedError` only from an allow-listed place.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"

#: Route functions that answer 403 themselves, and why the caller may know the object.
ROUTE_403 = {
    ("production.py", "_deployed_model"): "the API key authenticated; it is not scoped to that model",
    ("production.py", "get_model_info"): "the API key authenticated; it is not scoped to that model",
}

#: Service functions that raise PermissionDeniedError, and why the caller may know.
SERVICE_RAISES = {
    ("feature_store_service.py", "_owned_for_change"): "the caller can read the feature (shared or public)",
}


def _is_403(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "HTTPException"):
        return False
    for keyword in node.keywords:
        if keyword.arg == "status_code":
            value = keyword.value
            return getattr(value, "value", None) == 403 or getattr(value, "attr", None) == "HTTP_403_FORBIDDEN"
    return False


def _sites(path: Path, matches) -> list[tuple[str, str, bool]]:
    """(function, inside `except PermissionDeniedError`) for each match."""
    found = []

    def visit(node: ast.AST, function: str, mapped: bool) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function = node.name
        if isinstance(node, ast.ExceptHandler):
            mapped = getattr(node.type, "id", None) == "PermissionDeniedError"
        if matches(node):
            found.append((function, mapped))
        for child in ast.iter_child_nodes(node):
            visit(child, function, mapped)

    visit(ast.parse(path.read_text()), "<module>", False)
    return found


def test_a_route_answers_403_only_for_a_permission_the_caller_may_know_about():
    unexplained = [
        f"{path.name}:{function}"
        for path in sorted((APP / "api" / "routes").glob("*.py"))
        for function, mapped in _sites(path, _is_403)
        if not mapped and (path.name, function) not in ROUTE_403
    ]

    assert unexplained == [], "answer 404 as for an unknown id, or allow-list the 403 with its reason"


def test_a_service_raises_permission_denied_only_where_the_caller_may_know_the_object():
    def raises_denied(node: ast.AST) -> bool:
        return isinstance(node, ast.Raise) and getattr(getattr(node.exc, "func", None), "id", None) == "PermissionDeniedError"

    unexplained = [
        f"{path.name}:{function}"
        for path in sorted((APP / "services").rglob("*.py"))
        for function, _ in _sites(path, raises_denied)
        if (path.name, function) not in SERVICE_RAISES
    ]

    assert unexplained == [], "raise NotFoundError, or allow-list the raise with its reason"


def test_the_allow_lists_name_places_that_still_exist():
    """An entry whose 403 or raise is gone fails, so the lists shrink with the code."""
    routes = {
        (path.name, function)
        for path in (APP / "api" / "routes").glob("*.py")
        for function, mapped in _sites(path, _is_403)
        if not mapped
    }
    services = {
        (path.name, function)
        for path in (APP / "services").rglob("*.py")
        for function, _ in _sites(
            path,
            lambda n: isinstance(n, ast.Raise) and getattr(getattr(n.exc, "func", None), "id", None) == "PermissionDeniedError",
        )
    }

    assert set(ROUTE_403) <= routes and set(SERVICE_RAISES) <= services
