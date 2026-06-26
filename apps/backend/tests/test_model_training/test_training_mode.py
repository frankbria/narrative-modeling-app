"""Tests for Quick/Comprehensive training modes (issue #101)."""

from app.services.model_training.training_mode import (
    TrainingMode,
    normalize_mode,
    recommend_mode,
    resolve_mode_config,
)


class TestNormalizeMode:
    def test_known_strings(self):
        assert normalize_mode("quick") is TrainingMode.QUICK
        assert normalize_mode("COMPREHENSIVE") is TrainingMode.COMPREHENSIVE
        assert normalize_mode("  Quick ") is TrainingMode.QUICK

    def test_enum_passthrough(self):
        assert normalize_mode(TrainingMode.QUICK) is TrainingMode.QUICK

    def test_unknown_and_none(self):
        assert normalize_mode("bogus") is None
        assert normalize_mode(None) is None
        assert normalize_mode(123) is None


class TestResolveModeConfig:
    def test_quick_preset(self):
        config = resolve_mode_config("quick")
        assert config["training_mode"] == "quick"
        assert config["max_models"] == 3
        assert config["time_limit"] == 300
        assert config["enable_tuning"] is False
        assert config["early_stop_score"] == 0.95

    def test_comprehensive_preset(self):
        config = resolve_mode_config("comprehensive")
        assert config["training_mode"] == "comprehensive"
        assert config["max_models"] >= 10  # AC2: 10+ algorithms
        assert config["time_limit"] == 1800
        assert config["enable_tuning"] is True
        assert config["tuning_strategy"] == "bayesian"
        assert config["early_stop_score"] is None

    def test_comprehensive_tuning_budget_fits_time_limit(self):
        """Per-candidate tuning budget x candidates must fit the mode cap.

        Tuning runs before the loop-level time_limit check, so the up-front
        tuning phase must stay within the advertised cap on its own (codex
        review fix).
        """
        config = resolve_mode_config("comprehensive")
        per_candidate = config["tuning_config"]["time_budget"]
        worst_case_tuning = per_candidate * config["max_models"]
        assert worst_case_tuning <= config["time_limit"]

    def test_overrides_win(self):
        config = resolve_mode_config("quick", {"max_models": 7, "time_limit": 60})
        assert config["max_models"] == 7
        assert config["time_limit"] == 60
        # Untouched preset keys survive.
        assert config["enable_tuning"] is False

    def test_none_overrides_ignored(self):
        config = resolve_mode_config("quick", {"max_models": None})
        assert config["max_models"] == 3

    def test_unknown_mode_is_empty(self):
        assert resolve_mode_config("bogus") == {}
        assert resolve_mode_config(None) == {}

    def test_unknown_mode_keeps_overrides(self):
        # No mode but an explicit max_models still flows through unchanged.
        assert resolve_mode_config(None, {"max_models": 5}) == {"max_models": 5}


class TestRecommendMode:
    def test_small_dataset_recommends_comprehensive(self):
        rec = recommend_mode(500, 8)
        assert rec["recommended_mode"] == "comprehensive"
        assert "comprehensive" in rec["reason"].lower()

    def test_large_rows_recommends_quick(self):
        rec = recommend_mode(100_000, 8)
        assert rec["recommended_mode"] == "quick"

    def test_wide_dataset_recommends_quick(self):
        rec = recommend_mode(500, 80)
        assert rec["recommended_mode"] == "quick"

    def test_handles_none(self):
        rec = recommend_mode(None, None)
        assert rec["recommended_mode"] == "comprehensive"
