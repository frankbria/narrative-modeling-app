"""
Tests for AutoML engine
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.services.model_training.automl_engine import (
    AutoMLEngine,
    AutoMLResult,
    ModelCandidate,
    TrainingCancelledError,
    TrainingEvent,
)
from app.services.model_training.feature_engineer import FeatureEngineeringResult
from app.services.model_training.problem_detector import (
    ProblemDetectionResult,
    ProblemType,
)


class TestAutoMLEngine:
    """Test suite for AutoML engine"""

    @pytest.fixture
    def engine(self):
        """Create AutoML engine instance"""
        return AutoMLEngine(max_models=5, cv_folds=3, test_size=0.2, random_state=42)

    @pytest.fixture
    def classification_data(self):
        """Create classification dataset"""
        np.random.seed(42)
        n_samples = 200
        X = pd.DataFrame(
            {
                "feature1": np.random.randn(n_samples),
                "feature2": np.random.randn(n_samples),
                "feature3": np.random.choice(["A", "B", "C"], n_samples),
                "feature4": np.random.randint(0, 10, n_samples),
            }
        )
        y = pd.Series(np.random.choice([0, 1], n_samples, p=[0.4, 0.6]))
        return X, y

    @pytest.fixture
    def regression_data(self):
        """Create regression dataset"""
        np.random.seed(42)
        n_samples = 200
        X = pd.DataFrame(
            {
                "feature1": np.random.randn(n_samples),
                "feature2": np.random.randn(n_samples),
                "feature3": np.random.uniform(0, 100, n_samples),
                "category": np.random.choice(["X", "Y", "Z"], n_samples),
            }
        )
        # Create target with some relationship to features
        y = pd.Series(
            10
            + 2 * X["feature1"]
            + 3 * X["feature2"]
            + 0.1 * X["feature3"]
            + np.random.randn(n_samples)
        )
        return X, y

    @pytest.mark.asyncio
    async def test_run_classification_pipeline(self, engine, classification_data):
        """Test complete AutoML pipeline for classification"""
        X, y = classification_data
        df = pd.concat([X, pd.DataFrame({"target": y})], axis=1)

        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification detected",
            metadata={"unique_values": 2},
        )

        async def mock_detect(df, target):
            return mock_detection

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(df, "target")

        # Check result structure
        assert isinstance(result, AutoMLResult)
        assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
        assert isinstance(result.best_model, ModelCandidate)
        assert len(result.all_models) > 0
        assert result.training_time > 0

        # Check best model has scores
        assert result.best_model.cv_score is not None
        assert result.best_model.test_score is not None
        assert result.best_model.training_time is not None

        # Check metadata
        assert "n_samples" in result.metadata
        assert "n_features_original" in result.metadata
        assert result.metadata["n_samples"] == len(df)

    @pytest.mark.asyncio
    async def test_run_regression_pipeline(self, engine, regression_data):
        """Test complete AutoML pipeline for regression"""
        X, y = regression_data
        df = pd.concat([X, pd.DataFrame({"price": y})], axis=1)

        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.REGRESSION,
            target_column="price",
            confidence=0.95,
            reasoning="Regression problem detected",
            metadata={"target_stats": {"mean": 10.0, "std": 5.0}},
        )

        async def mock_detect(df, target):
            return mock_detection

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(df, "price")

        # Check result
        assert result.problem_type == ProblemType.REGRESSION
        assert result.best_model is not None
        assert all(m.cv_score is not None for m in result.all_models)

    @pytest.mark.asyncio
    async def test_get_candidate_models_classification(self, engine):
        """Test candidate model selection for classification"""
        candidates = engine._get_candidate_models(
            ProblemType.BINARY_CLASSIFICATION, (1000, 20)  # n_samples, n_features
        )

        # Check we get appropriate models
        model_names = [c.name for c in candidates]
        assert "Logistic Regression" in model_names
        assert "Random Forest" in model_names
        assert "XGBoost" in model_names
        assert "LightGBM" in model_names

        # KNN should be included for this size
        assert "K-Nearest Neighbors" in model_names

        # Check each candidate has required attributes
        for candidate in candidates:
            assert hasattr(candidate, "name")
            assert hasattr(candidate, "estimator")
            assert hasattr(candidate, "hyperparameters")

    @pytest.mark.asyncio
    async def test_get_candidate_models_large_dataset(self, engine):
        """Test candidate model selection for large datasets"""
        candidates = engine._get_candidate_models(
            ProblemType.BINARY_CLASSIFICATION, (50000, 100)  # Large dataset
        )

        model_names = [c.name for c in candidates]

        # SVM and Gradient Boosting should be excluded for large datasets
        assert "SVM" not in model_names
        assert "Gradient Boosting" not in model_names

        # Fast models should still be included
        assert "XGBoost" in model_names
        assert "LightGBM" in model_names

    def test_get_scoring_metric(self, engine):
        """Test scoring metric selection"""
        assert (
            engine._get_scoring_metric(ProblemType.BINARY_CLASSIFICATION) == "roc_auc"
        )
        assert (
            engine._get_scoring_metric(ProblemType.MULTICLASS_CLASSIFICATION)
            == "f1_weighted"
        )
        assert (
            engine._get_scoring_metric(ProblemType.REGRESSION)
            == "neg_mean_squared_error"
        )
        assert engine._get_scoring_metric(ProblemType.CLUSTERING) == "accuracy"

    def test_calculate_test_score(self, engine):
        """Test test score calculation"""
        y_true = pd.Series([0, 1, 0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 1, 1, 1])

        # Classification score (accuracy)
        score = engine._calculate_test_score(
            y_true, y_pred, ProblemType.BINARY_CLASSIFICATION
        )
        assert score == 5 / 6  # 5 correct out of 6

        # Regression score (R²)
        y_true_reg = pd.Series([1.0, 2.0, 3.0, 4.0])
        y_pred_reg = np.array([1.1, 1.9, 3.2, 3.8])
        score_reg = engine._calculate_test_score(
            y_true_reg, y_pred_reg, ProblemType.REGRESSION
        )
        assert 0.9 < score_reg < 1.0  # Should be close to 1

    def test_get_feature_importance_tree_model(self, engine):
        """Test feature importance extraction from tree-based models"""
        from sklearn.ensemble import RandomForestClassifier

        # Create and fit a simple model
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        X = np.random.randn(100, 3)
        y = np.random.choice([0, 1], 100)
        model.fit(X, y)

        feature_names = ["feat1", "feat2", "feat3"]
        importance = engine._get_feature_importance(model, feature_names)

        assert importance is not None
        assert len(importance) == 3
        assert all(0 <= v <= 1 for v in importance.values())
        assert sum(importance.values()) > 0

    def test_get_feature_importance_linear_model(self, engine):
        """Test feature importance extraction from linear models"""
        from sklearn.linear_model import LogisticRegression

        # Create and fit a simple model
        model = LogisticRegression(random_state=42)
        X = np.random.randn(100, 3)
        y = np.random.choice([0, 1], 100)
        model.fit(X, y)

        feature_names = ["feat1", "feat2", "feat3"]
        importance = engine._get_feature_importance(model, feature_names)

        assert importance is not None
        assert len(importance) == 3
        assert all(v >= 0 for v in importance.values())

    @pytest.mark.asyncio
    async def test_model_training_error_handling(self, engine, classification_data):
        """Test error handling during model training"""
        X, y = classification_data
        df = pd.concat([X, pd.DataFrame({"target": y})], axis=1)

        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        # Create a faulty model candidate
        faulty_model = MagicMock()
        faulty_model.fit.side_effect = Exception("Training failed")

        # Create a working model
        working_model = MagicMock()
        working_model.fit.return_value = None
        working_model.predict.return_value = np.array([0] * 40)  # For test set
        working_model.feature_importances_ = np.array([0.5, 0.3, 0.2, 0.1])

        async def mock_detect(df, target):
            return mock_detection

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            with patch.object(engine, "_get_candidate_models") as mock_candidates:
                mock_candidates.return_value = [
                    ModelCandidate(
                        name="Faulty Model", estimator=faulty_model, hyperparameters={}
                    ),
                    ModelCandidate(
                        name="Working Model",
                        estimator=working_model,
                        hyperparameters={},
                    ),
                ]

                # Mock cross_val_score to return good scores for working model
                with patch(
                    "app.services.model_training.automl_engine.cross_val_score"
                ) as mock_cv:
                    mock_cv.return_value = np.array([0.85, 0.87, 0.86])

                    # Should still complete even with one failing model
                    result = await engine.run(df, "target")

                    # Only successful models should be in results
                    assert len(result.all_models) == 1
                    assert result.all_models[0].name == "Working Model"
                    assert result.all_models[0].cv_score > 0.8

    @pytest.mark.asyncio
    async def test_max_models_limit(self, engine, classification_data):
        """Test that max_models limit is respected"""
        engine.max_models = 2
        X, y = classification_data
        df = pd.concat([X, pd.DataFrame({"target": y})], axis=1)

        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        async def mock_detect(df, target):
            return mock_detection

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(df, "target")

            # Should train at most max_models
            assert len(result.all_models) <= engine.max_models

    @pytest.mark.asyncio
    async def test_feature_engineering_integration(self, engine):
        """Test integration with feature engineering"""
        # Use simpler test without actual model training
        n_samples = 100
        X = pd.DataFrame(
            {
                "num1": np.random.randn(n_samples),
                "num2": np.random.randn(n_samples),
            }
        )
        y = pd.Series(np.random.choice([0, 1], n_samples))
        df = pd.concat([X, pd.DataFrame({"target": y})], axis=1)

        # Mock feature engineering result
        mock_feature_result = FeatureEngineeringResult(
            X_transformed=X,
            feature_names=list(X.columns),
            transformers={},
            feature_importance=None,
            metadata={"original_features": list(X.columns)},
        )

        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        async def mock_detect(df, target):
            return mock_detection

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):

            async def mock_fit_transform(X, y, problem_type):
                return mock_feature_result

            async def mock_transform(X):
                # Return data as-is since no categorical columns
                return X

            with patch.object(
                engine.feature_engineer, "fit_transform", side_effect=mock_fit_transform
            ):
                with patch.object(
                    engine.feature_engineer, "transform", side_effect=mock_transform
                ):
                    # Mock model candidates
                    mock_model = MagicMock()
                    mock_model.fit.return_value = None
                    mock_model.predict.return_value = np.array([0] * 20)
                    mock_model.feature_importances_ = np.array([0.6, 0.4])

                    with patch.object(
                        engine, "_get_candidate_models"
                    ) as mock_candidates:
                        mock_candidates.return_value = [
                            ModelCandidate(
                                name="Mock Model",
                                estimator=mock_model,
                                hyperparameters={},
                            )
                        ]

                        with patch(
                            "app.services.model_training.automl_engine.cross_val_score"
                        ) as mock_cv:
                            mock_cv.return_value = np.array([0.9, 0.91, 0.89])

                            result = await engine.run(df, "target")

                            # Check feature engineering metadata is included
                            assert "feature_engineering" in result.metadata
                            assert result.metadata["feature_engineering"][
                                "original_features"
                            ] == ["num1", "num2"]


class TestAutoMLEngineEnhancements:
    """Tests for class-imbalance handling, progress callbacks, and comparison."""

    @pytest.fixture
    def engine(self):
        return AutoMLEngine(max_models=3, cv_folds=3, test_size=0.2, random_state=42)

    @pytest.fixture
    def imbalanced_data(self):
        np.random.seed(42)
        n_samples = 200
        X = pd.DataFrame(
            {
                "feature1": np.random.randn(n_samples),
                "feature2": np.random.randn(n_samples),
            }
        )
        # 90/10 imbalance -> ratio 9:1, well above the 2:1 threshold
        y = pd.Series([0] * 180 + [1] * 20)
        df = pd.concat([X, pd.DataFrame({"target": y})], axis=1)
        return df

    def test_assess_class_balance_flags_imbalance(self, engine):
        y = pd.Series([0] * 80 + [1] * 20)  # 4:1
        ratio, weight = engine._assess_class_balance(y, is_classification=True)
        assert ratio == 4.0
        assert weight == "balanced"

    def test_assess_class_balance_balanced_data(self, engine):
        y = pd.Series([0] * 55 + [1] * 45)  # ~1.2:1
        ratio, weight = engine._assess_class_balance(y, is_classification=True)
        assert weight is None

    def test_assess_class_balance_regression(self, engine):
        y = pd.Series(np.random.randn(100))
        ratio, weight = engine._assess_class_balance(y, is_classification=False)
        assert ratio is None
        assert weight is None

    def test_candidate_models_apply_class_weight(self, engine):
        candidates = engine._get_candidate_models(
            ProblemType.BINARY_CLASSIFICATION, (1000, 20), class_weight="balanced"
        )
        by_name = {c.name: c for c in candidates}
        # Estimators that support class_weight should receive it.
        assert by_name["Logistic Regression"].estimator.class_weight == "balanced"
        assert by_name["Random Forest"].estimator.class_weight == "balanced"

    def test_all_candidates_build_with_class_weight(self, engine):
        """Threading class_weight must not break estimators that don't accept it.

        XGBoost, Gradient Boosting and KNN do not take a ``class_weight``; the
        full candidate list (small dataset -> includes SVM/KNN) must still build.
        """
        candidates = engine._get_candidate_models(
            ProblemType.BINARY_CLASSIFICATION, (1000, 20), class_weight="balanced"
        )
        names = {c.name for c in candidates}
        # All expected candidates present and constructed without error.
        assert {"XGBoost", "Gradient Boosting", "K-Nearest Neighbors", "SVM"} <= names
        for candidate in candidates:
            assert candidate.estimator is not None

    @pytest.mark.asyncio
    async def test_run_reports_progress(self, engine, imbalanced_data):
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        async def mock_detect(df, target):
            return mock_detection

        calls = []

        async def on_progress(completed, total, current):
            calls.append((completed, total, current))

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(
                imbalanced_data, "target", progress_callback=on_progress
            )

        # Callback fired for each candidate plus a final completion tick.
        assert len(calls) >= 2
        # Final tick reports all candidates completed with no current algorithm.
        final_completed, final_total, final_current = calls[-1]
        assert final_completed == final_total
        assert final_current is None
        # class_balance metadata reflects that balancing was applied.
        assert result.metadata["class_balance"]["balancing_applied"] is True
        assert result.metadata["class_balance"]["ratio"] > 2.0

    @pytest.mark.asyncio
    async def test_run_includes_model_comparison(self, engine, imbalanced_data):
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        async def mock_detect(df, target):
            return mock_detection

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(imbalanced_data, "target")

        comparison = result.metadata["model_comparison"]
        assert len(comparison) == len(result.all_models)
        # Ranked by CV score descending.
        scores = [row["cv_score"] for row in comparison]
        assert scores == sorted(scores, reverse=True)
        for row in comparison:
            assert set(row) >= {"algorithm", "cv_score", "test_score", "training_time"}

    @pytest.mark.asyncio
    async def test_progress_callback_error_does_not_break_training(
        self, engine, imbalanced_data
    ):
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        async def mock_detect(df, target):
            return mock_detection

        async def bad_callback(completed, total, current):
            raise RuntimeError("callback exploded")

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(
                imbalanced_data, "target", progress_callback=bad_callback
            )

        # Training still completes despite the failing callback.
        assert result.best_model is not None


class TestAutoMLEngineMonitoring:
    """Tests for cancellation checks and log/stage/candidate events (issue #76)."""

    @pytest.fixture
    def engine(self):
        return AutoMLEngine(max_models=2, cv_folds=3, test_size=0.2, random_state=42)

    @pytest.fixture
    def classification_df(self):
        np.random.seed(42)
        n_samples = 200
        df = pd.DataFrame(
            {
                "feature1": np.random.randn(n_samples),
                "feature2": np.random.randn(n_samples),
                "target": np.random.choice([0, 1], n_samples),
            }
        )
        return df

    @pytest.fixture
    def mock_detect(self):
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column="target",
            confidence=0.95,
            reasoning="Binary classification",
            metadata={},
        )

        async def _detect(df, target):
            return mock_detection

        return _detect

    @pytest.mark.asyncio
    async def test_cancel_check_true_raises_before_training(
        self, engine, classification_df, mock_detect
    ):
        """A truthy cancel_check stops training with TrainingCancelledError."""

        async def always_cancel():
            return True

        progress_calls = []

        async def on_progress(completed, total, current):
            progress_calls.append((completed, total, current))

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            with pytest.raises(TrainingCancelledError):
                await engine.run(
                    classification_df,
                    "target",
                    progress_callback=on_progress,
                    cancel_check=always_cancel,
                )

        # Cancelled before the first candidate even reported progress.
        assert progress_calls == []

    @pytest.mark.asyncio
    async def test_cancel_check_after_first_candidate(
        self, engine, classification_df, mock_detect
    ):
        """Cancellation between candidates trains only the earlier ones."""
        calls = {"n": 0}

        async def cancel_after_first():
            calls["n"] += 1
            return calls["n"] > 1  # allow candidate 1, cancel before candidate 2

        candidates_seen = []

        async def on_event(event):
            if event.candidate is not None:
                candidates_seen.append(event.candidate["algorithm"])

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            with pytest.raises(TrainingCancelledError):
                await engine.run(
                    classification_df,
                    "target",
                    event_callback=on_event,
                    cancel_check=cancel_after_first,
                )

        assert len(candidates_seen) == 1

    @pytest.mark.asyncio
    async def test_cancel_check_honored_before_finalization(
        self, engine, classification_df, mock_detect
    ):
        """A cancel arriving while the LAST candidate trains is still honored.

        The pre-candidate checks all pass; the flag flips only once every
        candidate has finished, so only the finalization check can see it.
        Without that check the run would complete despite the API having
        acknowledged the cancellation.
        """
        total = {"value": None}
        candidates_seen = []

        async def on_event(event):
            if event.candidate is not None:
                candidates_seen.append(event.candidate["algorithm"])
            elif event.message.endswith("candidate models"):
                total["value"] = int(event.message.split()[1])

        async def cancel_after_last_candidate():
            return total["value"] is not None and len(candidates_seen) == total["value"]

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            with pytest.raises(TrainingCancelledError):
                await engine.run(
                    classification_df,
                    "target",
                    event_callback=on_event,
                    cancel_check=cancel_after_last_candidate,
                )

        # Every candidate trained; cancellation was honored at finalization.
        assert len(candidates_seen) == total["value"]

    @pytest.mark.asyncio
    async def test_events_emitted_in_stage_order(
        self, engine, classification_df, mock_detect
    ):
        """Stages flow preprocessing -> training -> finalizing with a summary."""
        events: list[TrainingEvent] = []

        async def on_event(event):
            events.append(event)

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(
                classification_df, "target", event_callback=on_event
            )

        stages = [e.stage for e in events if e.stage is not None]
        assert stages[0] == "preprocessing"
        assert "training" in stages
        assert "finalizing" in stages
        # Ordered: every preprocessing index < training indexes < finalizing.
        assert max(i for i, s in enumerate(stages) if s == "preprocessing") < min(
            i for i, s in enumerate(stages) if s == "training"
        )
        assert max(i for i, s in enumerate(stages) if s == "training") < min(
            i for i, s in enumerate(stages) if s == "finalizing"
        )
        # Final summary names the best model.
        assert result.best_model.name in events[-1].message

    @pytest.mark.asyncio
    async def test_candidate_events_include_scores(
        self, engine, classification_df, mock_detect
    ):
        """Each trained candidate emits an event with its scores and timing."""
        events: list[TrainingEvent] = []

        async def on_event(event):
            events.append(event)

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(
                classification_df, "target", event_callback=on_event
            )

        candidate_events = [e for e in events if e.candidate is not None]
        assert len(candidate_events) == len(result.all_models)
        for event in candidate_events:
            assert set(event.candidate) >= {
                "algorithm",
                "cv_score",
                "test_score",
                "training_time",
            }
            assert event.candidate["cv_score"] is not None
            # The human-readable message carries the scores too.
            assert "cv_score" in event.message
            assert event.level == "info"
            assert event.stage == "training"

    @pytest.mark.asyncio
    async def test_event_callback_error_does_not_break_training(
        self, engine, classification_df, mock_detect
    ):
        """A failing event callback never interrupts the run."""

        async def bad_event_callback(event):
            raise RuntimeError("event callback exploded")

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(
                classification_df, "target", event_callback=bad_event_callback
            )

        assert result.best_model is not None

    @pytest.mark.asyncio
    async def test_cancel_check_error_treated_as_not_cancelled(
        self, engine, classification_df, mock_detect
    ):
        """A failing cancel_check is swallowed and training continues."""

        async def bad_cancel_check():
            raise RuntimeError("cancel check exploded")

        with patch.object(
            engine.problem_detector, "detect_problem_type", side_effect=mock_detect
        ):
            result = await engine.run(
                classification_df, "target", cancel_check=bad_cancel_check
            )

        assert result.best_model is not None
