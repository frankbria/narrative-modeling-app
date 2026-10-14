"""#917: every recipe the transformations routes return is built by `_recipe_response`.

That helper is where a recipe's owner id goes to its owner only (#914). Four handlers
used to build `RecipeResponse` inline. They returned the caller's own new recipe, so
nothing leaked, but a handler changed later to return someone else's would not have
gone through the rule.
"""

import ast
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "app" / "api" / "routes" / "transformations.py"


def _builders_of_recipe_response() -> set[str]:
    """The functions in the module that call `RecipeResponse(...)`."""
    builders = set()
    for function in ast.walk(ast.parse(MODULE.read_text())):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "RecipeResponse":
                builders.add(function.name)
    return builders


def test_only_the_owner_aware_helper_builds_a_recipe_response():
    assert _builders_of_recipe_response() == {"_recipe_response"}
