"""The model report assembles stored facts and never invents one (#795).

The report exists for someone who has to defend a prediction, so its only real
requirement is that every figure in it is traceable to what produced it. That makes
the interesting tests the *absence* tests: a model whose training job was never
recorded must say so, not show an empty leaderboard that reads like "nothing else
was tried", and not carry a baseline it did not measure.

This is the #536 rule applied to a new surface — a quality score a customer cannot
trust is worse than no score — and the reason every section carries a `provenance`
rather than a docstring promising good behaviour.
"""

from datetime import UTC, datetime

import pytest

from app.models.ml_model import MLModel
from app.models.training_job import JobStatus, ModelComparisonEntry, TrainingJob
from app.services.model_report import Provenance, build_model_report, render_markdown

USER = "report-user"


def _model(model_id: str = "m-report", **overrides) -> MLModel:
    defaults = dict(
        user_id=USER,
        dataset_id="ds-report",
        model_id=model_id,
        name="Churn model",
        problem_type="classification",
        algorithm="Random Forest",
        target_column="churned",
        feature_names=["tenure", "monthly_charges"],
        cv_score=0.87,
        test_score=0.85,
        training_time=12.5,
        model_size=2048,
        n_samples_train=800,
        n_features=2,
        model_path="s3://b/m.pkl",
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return MLModel(**defaults)


def _job(model_id: str = "m-report", **overrides) -> TrainingJob:
    defaults = dict(
        model_id=model_id,
        user_id=USER,
        dataset_id="ds-report",
        target_column="churned",
        status=JobStatus.COMPLETED,
        best_algorithm="Random Forest",
        best_model_explanation="Random Forest won on cross-validated accuracy.",
        model_comparison=[
            ModelComparisonEntry(
                algorithm="Random Forest", cv_score=0.87, test_score=0.85
            ),
            ModelComparisonEntry(
                algorithm="Logistic Regression", cv_score=0.79, test_score=0.78
            ),
        ],
    )
    defaults.update(overrides)
    return TrainingJob(**defaults)


class TestTheLeaderboardComesFromTheTrainingJob:
    @pytest.mark.asyncio
    async def test_every_algorithm_tried_is_listed_with_its_score(self, setup_database):
        await _model().insert()
        await _job().insert()

        report = await build_model_report(_model(), USER)

        assert report.leaderboard.provenance is Provenance.STORED
        names = [row.algorithm for row in report.leaderboard.rows]
        assert names == ["Random Forest", "Logistic Regression"]
        assert report.leaderboard.rows[0].cv_score == pytest.approx(0.87)
        # The winner is marked, not left for the reader to infer from ordering.
        assert report.leaderboard.rows[0].is_winner is True
        assert report.leaderboard.rows[1].is_winner is False

    @pytest.mark.asyncio
    async def test_why_the_winner_won_is_the_stored_explanation(self, setup_database):
        await _model().insert()
        await _job().insert()

        report = await build_model_report(_model(), USER)

        assert report.winner.provenance is Provenance.STORED
        assert "Random Forest won" in (report.winner.explanation or "")

    @pytest.mark.asyncio
    async def test_no_job_means_not_recorded_not_an_empty_leaderboard(
        self, setup_database
    ):
        """The distinction that matters: "nothing was recorded" vs "nothing was tried"."""
        await _model("m-nojob").insert()

        report = await build_model_report(_model("m-nojob"), USER)

        assert report.leaderboard.provenance is Provenance.NOT_RECORDED
        assert report.leaderboard.rows == []
        assert report.leaderboard.note  # says why, in words
        assert report.partial is True

    @pytest.mark.asyncio
    async def test_another_tenants_job_is_not_read(self, setup_database):
        await _model().insert()
        await _job(user_id="someone-else").insert()

        report = await build_model_report(_model(), USER)

        assert report.leaderboard.provenance is Provenance.NOT_RECORDED
        assert report.leaderboard.rows == []


class TestTheBaselineIsComputedNotInvented:
    @pytest.mark.asyncio
    async def test_majority_class_baseline_from_stored_labels(self, setup_database):
        await _model().insert()
        # 7 of 10 held-out rows are the majority class.
        artifacts = {
            "y_test": ["no"] * 7 + ["yes"] * 3,
            "y_pred": ["no"] * 10,
            "problem_type": "classification",
        }

        report = await build_model_report(_model(), USER, artifacts=artifacts)

        assert report.baseline.provenance is Provenance.COMPUTED
        assert report.baseline.score == pytest.approx(0.7)
        assert report.baseline.strategy == "majority_class"
        # It must be unmistakable that the training run did not do this.
        assert "report time" in (report.baseline.note or "").lower()

    @pytest.mark.asyncio
    async def test_regression_baseline_is_the_mean(self, setup_database):
        await _model(problem_type="regression").insert()
        artifacts = {"y_test": [1.0, 2.0, 3.0], "problem_type": "regression"}

        report = await build_model_report(
            _model(problem_type="regression"), USER, artifacts=artifacts
        )

        assert report.baseline.provenance is Provenance.COMPUTED
        assert report.baseline.strategy == "mean"

    @pytest.mark.asyncio
    async def test_no_artifacts_means_no_baseline(self, setup_database):
        await _model().insert()

        report = await build_model_report(_model(), USER, artifacts=None)

        assert report.baseline.provenance is Provenance.NOT_RECORDED
        assert report.baseline.score is None


class TestCaveatsAreRaisedFromRealFlags:
    @pytest.mark.asyncio
    async def test_in_sample_calibration_is_disclosed(self, setup_database):
        model = _model(is_calibrated=True, calibration_score_is_insample=True)
        await model.insert()

        report = await build_model_report(model, USER)

        assert any("calibrat" in c.lower() for c in report.caveats)

    @pytest.mark.asyncio
    async def test_an_early_stopped_run_says_not_every_candidate_was_tried(
        self, setup_database
    ):
        await _job(
            model_comparison=[
                ModelComparisonEntry(algorithm="Random Forest", cv_score=0.87)
            ]
        ).insert()

        model = _model(
            training_config={
                "early_stopped": True,
                "stop_reason": "time_budget_reached",
                "algorithms_evaluated": 1,
            }
        )
        report = await build_model_report(model, USER)

        assert any("stopped early" in c.lower() for c in report.caveats)

    @pytest.mark.asyncio
    async def test_a_model_with_nothing_stored_invents_nothing(self, setup_database):
        """The strongest form of AC2: no job, no artifacts, no SHAP."""
        await _model("m-bare").insert()

        report = await build_model_report(_model("m-bare"), USER)

        assert report.partial is True
        assert report.leaderboard.rows == []
        assert report.baseline.score is None
        assert report.drivers.features == []
        # Every unsupported section says so rather than rendering a blank.
        for section in (report.leaderboard, report.baseline, report.drivers):
            assert section.provenance is Provenance.NOT_RECORDED
            assert section.note


class TestMarkdown:
    @pytest.mark.asyncio
    async def test_renders_the_sections_and_names_their_sources(self, setup_database):
        await _model().insert()
        await _job().insert()

        md = render_markdown(await build_model_report(_model(), USER))

        assert "# Model report" in md
        assert "Random Forest" in md
        assert "Logistic Regression" in md
        # Provenance survives into the document — a reader of the exported file
        # must be able to tell a measured number from an absent one.
        assert "not recorded" in md.lower() or "Not recorded" in md

    @pytest.mark.asyncio
    async def test_absent_sections_are_visible_in_the_document(self, setup_database):
        await _model("m-bare2").insert()

        md = render_markdown(await build_model_report(_model("m-bare2"), USER))

        assert "not recorded" in md.lower()
        # No empty table that could be misread as "only one algorithm exists".
        assert "| Random Forest |" not in md


class TestReproducibilityReportsOnlyWhatWasCaptured:
    @pytest.mark.asyncio
    async def test_library_versions_come_from_environment_metadata(
        self, setup_database
    ):
        model = _model(
            environment_metadata={
                "python": "3.13.3",
                "sklearn": "1.5.0",
                "numpy": "2.0.1",
            }
        )
        await model.insert()

        report = await build_model_report(model, USER)

        assert report.reproducibility.provenance is Provenance.STORED
        assert report.reproducibility.environment["sklearn"] == "1.5.0"

    @pytest.mark.asyncio
    async def test_the_seed_is_not_claimed_because_it_is_not_stored(
        self, setup_database
    ):
        """`random_state=42` is an engine default, never written per model.

        Reporting "seed: 42" would be a guess that happens to be right today and
        silently wrong the moment a caller overrides it.
        """
        model = _model()
        await model.insert()

        report = await build_model_report(model, USER)

        assert report.reproducibility.seed is None

    @pytest.mark.asyncio
    async def test_a_missing_dataset_version_is_disclosed_as_a_caveat(
        self, setup_database
    ):
        """`dataset_version_id` is null in the normal flow (id-space mismatch),

        so the report must not imply the model knows which version it trained on.
        """
        model = _model(dataset_version_id=None)
        await model.insert()

        report = await build_model_report(model, USER)

        assert any("dataset version" in c.lower() for c in report.caveats)
