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

import math
import re
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


class TestReviewFindings:
    """Four defects found in review of #799, each pinned here."""

    @pytest.mark.asyncio
    async def test_time_series_regression_does_not_get_a_classification_baseline(
        self, setup_database
    ):
        """`startswith("regress")` is False for `time_series_regression`.

        It fell through to the majority-class branch, which counts distinct float
        labels and prints a ~1/N "accuracy" over continuous values — a fabricated
        number wearing a `computed_at_report_time` label, which is worse than the
        absence it was meant to prevent.
        """
        model = _model(problem_type="time_series_regression")
        await model.insert()
        artifacts = {
            "y_test": [1.5, 2.5, 3.5, 4.5],
            "problem_type": "time_series_regression",
        }

        report = await build_model_report(model, USER, artifacts=artifacts)

        assert report.baseline.strategy == "mean"
        assert report.baseline.metric == "mean_absolute_error"

    @pytest.mark.asyncio
    async def test_clustering_has_no_baseline_rather_than_a_meaningless_one(
        self, setup_database
    ):
        model = _model(problem_type="clustering")
        await model.insert()
        artifacts = {"y_test": [0, 1, 0, 2], "problem_type": "clustering"}

        report = await build_model_report(model, USER, artifacts=artifacts)

        assert report.baseline.provenance is Provenance.NOT_RECORDED
        assert report.baseline.score is None

    @pytest.mark.asyncio
    async def test_a_corrupt_shap_payload_does_not_raise(self, setup_database):
        """The route promises it never 500s on an owned model; a hand-edited or
        truncated S3 blob must degrade like `/shap` does, not propagate."""
        model = _model()
        await model.insert()

        report = await build_model_report(
            model, USER, shap_artifacts={"shap_importance": ["not", "a", "dict"]}
        )

        assert report.drivers.provenance is Provenance.NOT_RECORDED

    @pytest.mark.asyncio
    async def test_a_corrupt_y_test_does_not_raise(self, setup_database):
        model = _model()
        await model.insert()

        report = await build_model_report(model, USER, artifacts={"y_test": "oops"})

        assert report.baseline.provenance is Provenance.NOT_RECORDED

    @pytest.mark.asyncio
    async def test_a_pipe_in_a_feature_name_does_not_break_the_table(
        self, setup_database
    ):
        """Feature names come from uploaded CSV headers, which may contain `|`."""
        model = _model(feature_importance={"a|b": 0.9, "plain": 0.1})
        await model.insert()

        md = render_markdown(await build_model_report(model, USER))

        assert r"a\|b" in md
        # Structure is intact: exactly three UNESCAPED pipes (leading, middle,
        # trailing). The escaped one is still a pipe character, so count delimiters.
        rows = [line for line in md.split("\n") if line.startswith("| a")]
        assert rows, "the drivers table did not render"
        assert len(re.findall(r"(?<!\\)\|", rows[0])) == 3


class TestFreeTextCannotInjectStructure:
    """`MLModel.name` and `target_column` are free text, never newline-stripped
    upstream, and land in the document's heading and body (#799 round 2)."""

    @pytest.mark.asyncio
    async def test_a_newline_in_the_model_name_stays_on_the_heading_line(
        self, setup_database
    ):
        model = _model("m-inject")
        model.name = "Churn\n## Injected heading"
        await model.insert()

        md = render_markdown(await build_model_report(model, USER))

        assert md.splitlines()[0].startswith("# Model report — Churn")
        assert "\n## Injected heading" not in md

    @pytest.mark.asyncio
    async def test_a_carriage_return_in_a_feature_name_is_flattened(
        self, setup_database
    ):
        model = _model("m-cr", feature_importance={"a\rb": 0.5})
        await model.insert()

        md = render_markdown(await build_model_report(model, USER))

        assert "\r" not in md

    @pytest.mark.asyncio
    async def test_a_newline_in_the_stored_explanation_is_flattened(
        self, setup_database
    ):
        """Deterministic and LLM-free today, but #795 scopes generated prose as a
        later addition landing in exactly this field."""
        await _model("m-expl").insert()
        await _job(
            "m-expl", best_model_explanation="It won.\n## Not a real heading"
        ).insert()

        md = render_markdown(await build_model_report(_model("m-expl"), USER))

        assert "\n## Not a real heading" not in md
        assert "It won. ## Not a real heading" in md

    @pytest.mark.asyncio
    async def test_the_winner_is_stored_even_when_the_job_is_not(self, setup_database):
        """Its numbers come off MLModel and are always present.

        Labelling the whole section `not_recorded` because the *explanation* is
        missing marks real stored numbers as absent — the inverse of inventing one,
        and the same breach of the contract `provenance` exists to carry.
        """
        await _model("m-nojob2").insert()

        report = await build_model_report(_model("m-nojob2"), USER)

        assert report.winner.provenance is Provenance.STORED
        assert report.winner.cv_score == pytest.approx(0.87)
        # The absent half is carried by the note, not by mislabelling the whole.
        assert report.winner.explanation is None
        assert report.winner.note

    @pytest.mark.asyncio
    async def test_a_backtick_in_the_target_column_cannot_close_the_code_span(
        self, setup_database
    ):
        """CSV headers may legally contain a backtick."""
        model = _model("m-tick", target_column="weird`col")
        await model.insert()

        md = render_markdown(await build_model_report(model, USER))

        line = next(ln for ln in md.split("\n") if ln.startswith("- Target column:"))
        # A longer fence than any run inside, so the value survives verbatim.
        assert "weird`col" in line
        assert line.startswith("- Target column: ``")

    @pytest.mark.asyncio
    async def test_a_non_string_problem_type_does_not_500(self, setup_database):
        """The artifact blob is hand-editable JSON; `problem_type` may not be a str."""
        await _model("m-badtype").insert()

        report = await build_model_report(
            _model("m-badtype"), USER, artifacts={"y_test": [1, 2], "problem_type": 7}
        )

        assert report.baseline.provenance is Provenance.NOT_RECORDED

    @pytest.mark.asyncio
    async def test_a_newline_in_a_note_does_not_inject_a_heading(self, setup_database):
        await _model("m-note").insert()

        report = await build_model_report(
            _model("m-note"),
            USER,
            artifacts={"y_test": [1, 2], "problem_type": "clustering\n## Injected"},
        )
        md = render_markdown(report)

        # Case-insensitive: `_baseline` lower-cases `kind` before it reaches the
        # note, so asserting the capitalised form passed even with the flattening
        # deleted — the first version of this test could not fail.
        assert "\n## injected" not in md.lower()
        # Stronger and independent of this payload: the only headings in the
        # document are the ones the renderer itself writes.
        headings = {ln for ln in md.split("\n") if ln.startswith("#")}
        assert headings <= {
            f"# Model report — {report.model_name}",
            "## The data",
            "## Algorithms tried",
            "## Baseline",
            "## Why this model",
            "## What drives it",
            "## Caveats",
            "## Reproducibility",
        }, headings

    @pytest.mark.asyncio
    async def test_a_missing_explanation_is_not_rendered_as_not_recorded(
        self, setup_database
    ):
        """The winner's numbers ARE stored; only the narrative is absent.

        Printing the same "_Not recorded._" used for genuinely absent sections is
        the round-4 mislabelling again, one layer down in the rendering.
        """
        await _model("m-noexpl").insert()

        md = render_markdown(await build_model_report(_model("m-noexpl"), USER))

        why = md.split("## Why this model")[1].split("##")[0]
        assert "Random Forest" in why
        assert "Not recorded" not in why

    @pytest.mark.asyncio
    async def test_a_nan_label_does_not_produce_a_nan_baseline(self, setup_database):
        """`float("nan")` does not raise, and json.loads parses bare NaN literals.

        A NaN score renders as "**nan**" labelled computed_at_report_time, and
        Starlette's `allow_nan=False` dump turns it into a 500 on an owned model —
        the third way this route could have broken its never-500 guarantee.
        """
        model = _model("m-nan", problem_type="regression")
        await model.insert()

        report = await build_model_report(
            model,
            USER,
            artifacts={"y_test": [1.0, float("nan")], "problem_type": "regression"},
        )

        assert report.baseline.provenance is Provenance.NOT_RECORDED
        assert report.baseline.score is None

    @pytest.mark.asyncio
    async def test_a_truncated_driver_list_says_so(self, setup_database):
        model = _model(
            "m-many", feature_importance={f"f{i}": i / 100 for i in range(35)}
        )
        await model.insert()

        report = await build_model_report(model, USER)
        md = render_markdown(report)

        assert len(report.drivers.features) == 20
        assert "of 35 features" in (report.drivers.note or "")
        assert "of 35 features" in md

    @pytest.mark.asyncio
    async def test_huge_labels_do_not_produce_an_infinite_baseline(
        self, setup_database
    ):
        """Finite inputs, non-finite result: [1e308, 1e308] overflows inside the sum.

        Guarding the inputs was not enough — the arithmetic has to be checked too.
        """
        model = _model("m-huge", problem_type="regression")
        await model.insert()

        report = await build_model_report(
            model,
            USER,
            artifacts={"y_test": [1e308, 1e308, -1e308], "problem_type": "regression"},
        )

        assert report.baseline.score is None or math.isfinite(report.baseline.score)

    @pytest.mark.asyncio
    async def test_an_oversized_integer_label_does_not_raise(self, setup_database):
        """`float(10**400)` raises OverflowError, an ArithmeticError — not caught by
        a `(TypeError, ValueError)` handler. json.loads produces ints this large."""
        model = _model("m-bigint", problem_type="regression")
        await model.insert()

        report = await build_model_report(
            model,
            USER,
            artifacts={"y_test": [10**400, 1], "problem_type": "regression"},
        )

        assert report.baseline.provenance is Provenance.NOT_RECORDED

    @pytest.mark.asyncio
    async def test_a_nan_feature_importance_is_dropped_not_served(self, setup_database):
        """The same non-question as the baseline had, one function up."""
        model = _model(
            "m-nanfeat", feature_importance={"good": 0.5, "bad": float("nan")}
        )
        await model.insert()

        report = await build_model_report(model, USER)

        names = [name for name, _ in report.drivers.features]
        assert names == ["good"]
