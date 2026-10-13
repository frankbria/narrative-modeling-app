"""#687: why a batch job's per-row errors are written as they are.

A row that cannot be predicted gets ``{"error": str(e), ...}`` in the job's results.
Everywhere else an exception's text is kept from the client (#269, #518, #637), because
it can name a bucket, a key or a host. Here it cannot: by the time a row is predicted
the model and its feature engineer are in memory, and the per-row path awaits nothing
but in-memory work. What its exceptions can say is the row's own values and column
names, and the message templates of open-source libraries ("could not convert string to
float: 'n/a'"), which is exactly what tells the owner of the file how to fix the row.

That reasoning holds only while the path stays in memory, so this test pins it. If it
fails because the path gained a storage or network call, do not extend the list: give
the row a fixed reason (see ``user_safe_failure_reason``) and log the exception.
"""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app/services/batch_prediction.py"

#: The per-row prediction path, and everything it is allowed to wait for.
PER_ROW_PATH = {
    "_predict_chunk",
    "_predict_chunk_vectorized",
    "_predict_chunk_sequential",
    "_attach_explanations",
}
IN_MEMORY = {
    "self._predict_chunk_vectorized",
    "self._predict_chunk_sequential",
    "self._attach_explanations",
    "feature_engineer.transform",  # fitted transformers, already loaded
    # The two wrappers run whatever they are handed, so they are listed with it.
    "run_locked_inference(lambda: _infer(X_transformed))",  # the loaded estimator, behind its lock
    "asyncio.to_thread(self.interpretability.compute_instance_shap_batch)",  # SHAP, off the event loop
}
#: Calls that run a callable given to them, and which argument that is.
RUNS_ITS_ARGUMENT = {"asyncio.to_thread": 0, "run_locked_inference": -1}


def _what_is_awaited(awaited: ast.expr) -> str:
    """The awaited expression as text. A wrapper is named with the callable it runs,
    since `await asyncio.to_thread(download, key)` waits for the download; anything
    that is not a call (a coroutine built earlier) is its own text, which no list has."""
    if not isinstance(awaited, ast.Call):
        return ast.unparse(awaited)
    name = ast.unparse(awaited.func)
    if name not in RUNS_ITS_ARGUMENT:
        return name
    return f"{name}({ast.unparse(awaited.args[RUNS_ITS_ARGUMENT[name]])})"


def _awaited(function: ast.AsyncFunctionDef) -> set[str]:
    return {_what_is_awaited(node.value) for node in ast.walk(function) if isinstance(node, ast.Await)}


def test_the_per_row_path_waits_for_nothing_but_in_memory_work():
    functions = {
        node.name: node
        for node in ast.walk(ast.parse(SOURCE.read_text()))
        if isinstance(node, ast.AsyncFunctionDef) and node.name in PER_ROW_PATH
    }

    assert set(functions) == PER_ROW_PATH, "a per-row function was renamed: update PER_ROW_PATH"
    reached = set().union(*(_awaited(function) for function in functions.values()))
    assert reached <= IN_MEMORY, f"the per-row path now awaits {sorted(reached - IN_MEMORY)}"


def test_the_row_errors_are_written_only_on_that_path():
    """The two places a row's exception text is written: a chunk that failed as a whole
    (around the call to ``_predict_chunk``) and a single row inside the sequential path."""
    source = SOURCE.read_text()

    assert source.count('"error": str(e)') == 2
