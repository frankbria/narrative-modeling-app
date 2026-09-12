"""Per-tier training ceilings (#500): one source of truth in ``plans.py``."""

from app.billing.plans import TRAINING_CEILINGS, training_ceilings_for
from app.models.subscription import PlanTier
from app.services.model_training.training_mode import TrainingMode, resolve_mode_config


def test_every_tier_has_finite_positive_ceilings():
    for tier in PlanTier:
        c = training_ceilings_for(tier)
        for name in (
            "max_models",
            "cv_folds",
            "time_limit_seconds",
            "wall_clock_seconds",
            "tuning_trials",
            "tuning_time_budget_seconds",
            "max_features",
        ):
            assert getattr(c, name) > 0, f"{tier}.{name} must be a finite positive ceiling"
        # The hard kill must never fire before the soft budget a caller may ask for.
        assert c.wall_clock_seconds >= c.time_limit_seconds


def test_ceilings_are_monotonic_by_tier():
    free, pro, ent = (
        training_ceilings_for(t) for t in (PlanTier.FREE, PlanTier.PRO, PlanTier.ENTERPRISE)
    )
    for name in ("max_models", "time_limit_seconds", "wall_clock_seconds", "tuning_trials"):
        assert getattr(free, name) <= getattr(pro, name) <= getattr(ent, name), name


def test_unknown_tier_falls_back_to_free():
    assert training_ceilings_for("nope") is TRAINING_CEILINGS[PlanTier.FREE]  # type: ignore[arg-type]


def test_server_presets_fit_the_free_ceilings():
    """A FREE user must still be able to pick every training mode the UI offers."""
    free = training_ceilings_for(PlanTier.FREE)
    for mode in TrainingMode:
        preset = resolve_mode_config(mode)
        assert preset["max_models"] <= free.max_models, mode
        assert preset["time_limit"] <= free.time_limit_seconds, mode
        tuning = preset.get("tuning_config") or {}
        assert tuning.get("n_trials", 0) <= free.tuning_trials, mode
        assert tuning.get("time_budget", 0) <= free.tuning_time_budget_seconds, mode
