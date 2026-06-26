"""Quick / Comprehensive training modes (issue #101).

A *training mode* is a named preset that maps to ``AutoMLEngine`` kwargs:

- **Quick** — a handful of fast, strong algorithms, default hyperparameters and
  a ~5 minute wall-clock cap, stopping early once a candidate is clearly good.
- **Comprehensive** — the full algorithm catalog with hyperparameter tuning and
  a 30 minute budget, for the best achievable model.

Modes ride inside the existing ``training_config`` dict (like #77's tuning
flags) — no request-schema change, no new ``MLModel`` field. ``resolve_mode_config``
turns a mode into engine kwargs; an absent/unknown mode yields ``{}`` so callers
keep today's behaviour unchanged.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

# Engine kwargs honoured when copied out of a resolved mode config.
_ENGINE_KEYS = (
    "max_models",
    "time_limit",
    "cv_folds",
    "test_size",
    "enable_tuning",
    "early_stop_score",
)

# Recommend Quick once a dataset is large enough that a tuned, full-catalog run
# would blow the budget. ponytail: simple size thresholds, revisit if users want
# accuracy-vs-time weighting.
_LARGE_ROWS = 50_000
_LARGE_FEATURES = 50


class TrainingMode(str, Enum):
    """Supported training modes."""

    QUICK = "quick"
    COMPREHENSIVE = "comprehensive"


# Per-mode AutoMLEngine presets.
_MODE_PRESETS: dict[TrainingMode, dict[str, Any]] = {
    TrainingMode.QUICK: {
        "max_models": 3,  # ~3 algorithms (AC1)
        "time_limit": 300,  # ~5 min cap (AC1)
        "enable_tuning": False,  # default hyperparameters (AC1)
        "early_stop_score": 0.95,  # stop once a candidate is clearly good (AC4)
    },
    TrainingMode.COMPREHENSIVE: {
        "max_models": 12,  # full catalog, 10+ algorithms (AC2)
        "time_limit": 1800,  # 30 min allowed (AC2)
        "enable_tuning": True,  # full tuning (AC2)
        "tuning_strategy": "bayesian",
        "early_stop_score": None,  # thorough: don't cut the search short
    },
}


def normalize_mode(mode: Any) -> TrainingMode | None:
    """Coerce a value to a ``TrainingMode``; ``None`` for anything unknown."""
    if mode is None:
        return None
    if isinstance(mode, TrainingMode):
        return mode
    try:
        return TrainingMode(str(mode).strip().lower())
    except ValueError:
        return None


def resolve_mode_config(
    mode: Any, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Map a training mode to engine config; explicit overrides win.

    Returns the preset for ``mode`` (with a ``training_mode`` marker), with any
    non-``None`` value in ``overrides`` taking precedence so a caller can still
    pin ``max_models``/``time_limit`` etc. An unknown or ``None`` mode yields an
    empty dict (minus surviving overrides), preserving pre-#101 behaviour.
    """
    normalized = normalize_mode(mode)
    config: dict[str, Any] = dict(_MODE_PRESETS.get(normalized, {})) if normalized else {}
    if normalized:
        config["training_mode"] = normalized.value
    for key, value in (overrides or {}).items():
        if value is not None:
            config[key] = value
    return config


def recommend_mode(n_rows: int | None, n_features: int | None) -> dict[str, Any]:
    """Recommend a mode from dataset size, with plain-language reasoning."""
    rows = n_rows or 0
    features = n_features or 0
    if rows > _LARGE_ROWS or features > _LARGE_FEATURES:
        mode = TrainingMode.QUICK
        reason = (
            f"{rows:,} rows x {features} features is large — Quick mode keeps "
            "training tractable (~5 min) while still comparing strong algorithms."
        )
    else:
        mode = TrainingMode.COMPREHENSIVE
        reason = (
            f"{rows:,} rows x {features} features is small enough to afford a "
            "thorough search — Comprehensive mode tunes 10+ algorithms for the "
            "best model."
        )
    return {"recommended_mode": mode.value, "reason": reason}


if __name__ == "__main__":  # pragma: no cover - runnable self-check (ponytail)
    assert resolve_mode_config("quick")["max_models"] == 3
    assert resolve_mode_config("quick")["time_limit"] == 300
    assert resolve_mode_config("comprehensive")["enable_tuning"] is True
    assert resolve_mode_config("comprehensive", {"max_models": 4})["max_models"] == 4
    assert resolve_mode_config("bogus") == {}
    assert resolve_mode_config(None) == {}
    assert recommend_mode(100, 5)["recommended_mode"] == "comprehensive"
    assert recommend_mode(100_000, 5)["recommended_mode"] == "quick"
    assert recommend_mode(100, 80)["recommended_mode"] == "quick"
    print("training_mode self-check passed")
