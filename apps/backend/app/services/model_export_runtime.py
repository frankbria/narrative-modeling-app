"""Helpers that make the model export runnable without the platform code (#632).

The Docker/Python export used to pickle the platform's own ``FeatureEngineer``,
whose module imports ``app.*`` — so the delivered container (no ``app`` package)
raised ``ModuleNotFoundError`` on load and never served a model trained with
feature engineering. Instead we ship:

  - a plain **state dict** (``feature_engineer_state``) — only fitted stock
    scikit-learn transformers plus lists/strings, no ``app`` class references, so
    it unpickles anywhere scikit-learn is installed; and
  - a self-contained ``feature_engineer.py`` (``standalone_module_source``) that
    reconstructs the transform from that dict, synchronously.
"""

from pathlib import Path
from typing import Any

_STANDALONE_MODULE = Path(__file__).parent / "model_export_assets" / "_standalone_fe.py"


def feature_engineer_state(feature_engineer: Any) -> dict[str, Any] | None:
    """Extract the shippable preprocessing state from a fitted ``FeatureEngineer``.

    Returns ``None`` when there is nothing to apply — no engineer, or one fitted
    with no transformers (``transformers == {}``) — which the container already
    handles as "no preprocessing" (the only case that worked before #632). The
    returned dict holds only stock sklearn objects and plain data, so it carries
    no reference to any ``app`` class.
    """
    if feature_engineer is None:
        return None
    transformers = getattr(feature_engineer, "transformers", None) or {}
    if not transformers:
        return None
    config = getattr(feature_engineer, "config", None)
    return {
        "encoding_method": getattr(config, "encoding_method", "onehot"),
        "transformers": transformers,
        "numeric_features": list(getattr(feature_engineer, "numeric_features", [])),
        "categorical_features": list(getattr(feature_engineer, "categorical_features", [])),
        "feature_names": list(getattr(feature_engineer, "feature_names", [])),
    }


def standalone_module_source() -> str:
    """The source of the standalone ``feature_engineer.py`` to ship in the export."""
    return _STANDALONE_MODULE.read_text()
