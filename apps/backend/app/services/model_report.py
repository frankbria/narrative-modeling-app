"""Assemble a defensible account of a trained model from what was stored (#795).

The reader of this document has to defend a prediction to someone who can reject
it. That makes the design rule simple and absolute: **every figure is traceable to
what produced it, or it is absent and says so.**

Hence `Provenance` on every section. The alternative — rendering a blank table for
a model whose training job was never recorded — reads as "nothing else was tried",
which is a claim the data does not support. #536 is the precedent: a quality score a
customer cannot trust is worse than no score.

What is deliberately NOT claimed, because the platform does not record it:

* **the random seed** — `random_state=42` is an engine default
  (`automl_engine.py`), never written per model. Printing "seed: 42" would be a
  guess that is right today and silently wrong the first time a caller overrides it;
* **the dataset version** — `MLModel.dataset_version_id` is null in the normal flow
  (the resolver queries the `DatasetVersion` id-space with a `UserData` ObjectId, so
  it never matches). Surfaced as a caveat rather than left to imply currency;
* **the preprocessing actually applied** — no ordered list is reachable from a model.
  `UserData.transformation_history` is never written, `pipeline/apply` records
  nothing, and reconstructing the chain needs a join through a mutating `s3_url`;
* **the winner's hyperparameters** — dropped when the comparison rows are built,
  except for whatever tuning recorded.

Each of those is a `not_recorded` section or a caveat, and each is a candidate for a
later issue that captures the data at training time. None of them is a reason to
print a plausible number.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.ml_model import MLModel
from app.models.training_job import TrainingJob
from app.utils.datetime import as_utc


class Provenance(str, Enum):
    """Where a section's numbers came from. Rendered into the document itself."""

    STORED = "stored"
    """Read back from what the training run wrote down."""

    COMPUTED = "computed_at_report_time"
    """Derived here from stored raw data — real, but the run did not do it."""

    NOT_RECORDED = "not_recorded"
    """The platform never captured this. Not "zero", not "none tried"."""


class Section(BaseModel):
    provenance: Provenance
    note: str | None = None


class LeaderboardRow(BaseModel):
    algorithm: str
    cv_score: float | None = None
    test_score: float | None = None
    training_time: float | None = None
    is_winner: bool = False


class LeaderboardSection(Section):
    rows: list[LeaderboardRow] = Field(default_factory=list)


class WinnerSection(Section):
    algorithm: str
    cv_score: float | None = None
    test_score: float | None = None
    explanation: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class BaselineSection(Section):
    strategy: str | None = None
    score: float | None = None
    metric: str | None = None


class DriversSection(Section):
    features: list[tuple[str, float]] = Field(default_factory=list)
    explainer_type: str | None = None


class DatasetSection(Section):
    target_column: str
    n_samples_train: int | None = None
    n_features: int | None = None
    feature_names: list[str] = Field(default_factory=list)


class ReproducibilitySection(Section):
    environment: dict[str, str] = Field(default_factory=dict)
    seed: int | None = None
    dataset_version_id: str | None = None
    training_config: dict[str, Any] = Field(default_factory=dict)


class ModelReport(BaseModel):
    model_id: str
    model_name: str
    problem_type: str
    generated_at: datetime
    trained_at: datetime | None = None
    partial: bool = False

    dataset: DatasetSection
    leaderboard: LeaderboardSection
    winner: WinnerSection
    baseline: BaselineSection
    drivers: DriversSection
    reproducibility: ReproducibilitySection
    caveats: list[str] = Field(default_factory=list)


_MAX_DRIVERS = 20
_NO_JOB_NOTE = (
    "No training job is recorded for this model, so the algorithms tried and their "
    "scores are unavailable. This is not a statement that only one algorithm was "
    "tried — the comparison was simply never written down for this run."
)
_NO_ARTIFACTS_NOTE = (
    "No held-out evaluation data is stored for this model, so a baseline cannot be "
    "computed from it."
)
_BASELINE_NOTE = (
    "Computed at report time from the stored held-out labels. The training run did "
    "not evaluate a baseline, so this is the report's own calculation — a model that "
    "does not clear it has not learned anything useful."
)


def _baseline(artifacts: dict[str, Any] | None, problem_type: str) -> BaselineSection:
    """The score a no-skill predictor gets on the SAME held-out labels.

    A pure function of `y_test`, which is why it can be stated honestly for models
    trained long before this feature existed.
    """
    y_test = (artifacts or {}).get("y_test")
    # A stored artifact is a JSON blob that can be truncated or hand-edited; the
    # route promises it never 500s on an owned model, so a wrong shape degrades
    # exactly like `/shap` does rather than propagating a TypeError.
    if not isinstance(y_test, (list, tuple)) or not y_test:
        return BaselineSection(
            provenance=Provenance.NOT_RECORDED, note=_NO_ARTIFACTS_NOTE
        )

    # `str(...)` before `.lower()`: `problem_type` comes from the artifact blob,
    # which is hand-editable JSON — a truthy non-string (a number, a list) raised
    # AttributeError and 500'd both report routes on an owned model.
    raw_kind = (artifacts or {}).get("problem_type") or problem_type or ""
    kind = str(raw_kind).lower()
    # Substring, not `startswith`: the problem types in use include
    # `time_series_regression` and `time_series_classification`, so a prefix test
    # sent every time-series regression into the majority-class branch and printed
    # a ~1/N "accuracy" over continuous labels — a fabricated number wearing a
    # computed-at-report-time label.
    if "regress" in kind:
        # Validate the RESULT, not just the inputs. Guarding the inputs alone left
        # two holes: a big JSON integer raises OverflowError (an ArithmeticError,
        # not a ValueError) during conversion, and finite-but-huge labels such as
        # [1e308, 1e308] overflow to inf inside the sum. Either way a non-finite
        # score reaches the response, where Starlette's `allow_nan=False` dump 500s
        # an owned model and the .md prints "**nan**" labelled computed_at_report_time.
        try:
            values = [float(v) for v in y_test]
            mean = sum(values) / len(values)
            ss_res = sum((v - mean) ** 2 for v in values)
            # R² of the mean predictor is 0 by definition; report MAE, which is a
            # number the reader can compare against the model's own error.
            mae = sum(abs(v - mean) for v in values) / len(values)
        except (TypeError, ValueError, ArithmeticError):
            mae = ss_res = float("nan")
        if not math.isfinite(mae):
            return BaselineSection(
                provenance=Provenance.NOT_RECORDED,
                note="The stored held-out labels do not yield a finite baseline, so "
                "none is shown.",
            )
        return BaselineSection(
            provenance=Provenance.COMPUTED,
            strategy="mean",
            score=mae,
            metric="mean_absolute_error",
            note=_BASELINE_NOTE
            + (" R² of a mean predictor is 0 by construction." if ss_res else ""),
        )

    if "classif" not in kind:
        return BaselineSection(
            provenance=Provenance.NOT_RECORDED,
            note=(
                f"No no-skill baseline is defined for a {kind or 'unknown'} problem, "
                "so none is shown."
            ),
        )

    counts = Counter(str(v) for v in y_test)
    majority = counts.most_common(1)[0][1]
    return BaselineSection(
        provenance=Provenance.COMPUTED,
        strategy="majority_class",
        score=majority / len(y_test),
        metric="accuracy",
        note=_BASELINE_NOTE,
    )


def _caveats(model: MLModel, job: TrainingJob | None) -> list[str]:
    """Only caveats a stored flag actually supports."""
    out: list[str] = []
    config = getattr(model, "training_config", None) or {}

    if getattr(model, "is_calibrated", False) and getattr(
        model, "calibration_score_is_insample", True
    ):
        out.append(
            "Probability calibration was fitted and scored on the same data, so the "
            "calibration quality shown is optimistic (#201)."
        )
    if getattr(model, "evaluation_on_calibration_set", False):
        out.append(
            "The held-out metrics were measured on the same split used to calibrate, "
            "so they are optimistic."
        )
    if config.get("early_stopped"):
        reason = config.get("stop_reason") or "unspecified"
        out.append(
            f"The run stopped early ({reason}), so not every candidate algorithm was "
            "tried. A better model may exist among the ones never reached."
        )
    if not getattr(model, "dataset_version_id", None):
        out.append(
            "This model does not record which dataset version it trained on, so the "
            "dataset described here is identified by id only and may have been "
            "transformed since."
        )
    if job is None:
        out.append(
            "No training job is recorded, so the algorithms tried and the reason this "
            "one won are unavailable."
        )
    return out


async def build_model_report(
    model: MLModel,
    user_id: str,
    artifacts: dict[str, Any] | None = None,
    shap_artifacts: dict[str, Any] | None = None,
) -> ModelReport:
    """Assemble the report. Reads only; never writes, never calls a model."""
    job = await TrainingJob.find_one(
        TrainingJob.model_id == model.model_id, TrainingJob.user_id == user_id
    )

    if job and job.model_comparison:
        winner_name = job.best_algorithm or model.algorithm
        rows = [
            LeaderboardRow(
                algorithm=entry.algorithm,
                cv_score=entry.cv_score,
                test_score=entry.test_score,
                training_time=entry.training_time,
                is_winner=entry.algorithm == winner_name,
            )
            for entry in job.model_comparison
        ]
        leaderboard = LeaderboardSection(provenance=Provenance.STORED, rows=rows)
    else:
        leaderboard = LeaderboardSection(
            provenance=Provenance.NOT_RECORDED, note=_NO_JOB_NOTE
        )

    # STORED unconditionally: `algorithm`, `cv_score` and `test_score` come off the
    # already-loaded MLModel and are always present. Only the "why it won" narrative
    # depends on the TrainingJob, and its absence is carried by `note`. Marking the
    # whole section NOT_RECORDED labelled real stored numbers as absent — the
    # inverse of fabricating one, and the same contract breach.
    winner = WinnerSection(
        provenance=Provenance.STORED,
        algorithm=model.algorithm,
        cv_score=model.cv_score,
        test_score=model.test_score,
        explanation=(job.best_model_explanation if job else None),
        metrics=getattr(model, "metrics", {}) or {},
        note=(
            None
            if job and job.best_model_explanation
            else "No stored explanation of why this algorithm won."
        ),
    )

    importance = getattr(model, "feature_importance", None) or {}
    shap_importance = (shap_artifacts or {}).get("shap_importance")
    # Same reasoning as `y_test` above — this is a raw S3 blob, not a validated model.
    if not isinstance(shap_importance, dict):
        shap_importance = {}
    if not isinstance(importance, dict):
        importance = {}
    ranked = shap_importance or importance
    ranked_features = sorted(
        _numeric_pairs(ranked), key=lambda kv: abs(kv[1]), reverse=True
    )
    if ranked_features:
        drivers = DriversSection(
            provenance=Provenance.STORED,
            features=ranked_features[:_MAX_DRIVERS],
            explainer_type=(
                getattr(model, "shap_explainer_type", None)
                if shap_importance
                else "model_native_importance"
            ),
            # "Here are the drivers" is an implicit claim when the tail is dropped
            # without saying so — the same shape the rest of the module avoids.
            note=(
                f"Showing the top {_MAX_DRIVERS} of {len(ranked_features)} features "
                "by magnitude."
                if len(ranked_features) > _MAX_DRIVERS
                else None
            ),
        )
    else:
        drivers = DriversSection(
            provenance=Provenance.NOT_RECORDED,
            note=(
                "Neither SHAP values nor model-native feature importance were stored "
                "for this model — some algorithms do not expose either."
            ),
        )

    environment = getattr(model, "environment_metadata", None) or {}
    reproducibility = ReproducibilitySection(
        provenance=Provenance.STORED if environment else Provenance.NOT_RECORDED,
        environment={str(k): str(v) for k, v in environment.items()},
        # Deliberately None — see the module docstring.
        seed=None,
        dataset_version_id=getattr(model, "dataset_version_id", None),
        training_config=getattr(model, "training_config", None) or {},
        note=(
            None
            if environment
            else "No library versions were captured when this model was trained."
        ),
    )

    dataset = DatasetSection(
        provenance=Provenance.STORED,
        target_column=model.target_column,
        n_samples_train=model.n_samples_train,
        n_features=model.n_features,
        feature_names=list(model.feature_names or []),
    )

    baseline = _baseline(artifacts, model.problem_type)
    sections = (leaderboard, winner, baseline, drivers, reproducibility, dataset)

    return ModelReport(
        model_id=model.model_id,
        model_name=model.name,
        problem_type=model.problem_type,
        generated_at=datetime.now(UTC),
        # `as_utc`: Mongo reads datetimes back NAIVE, so this serialized with no
        # offset and the page parsed the zone-less string as the VIEWER's local
        # zone — a wrong training time for every non-UTC reader, in a document
        # whose whole purpose is being checkable.
        trained_at=(
            as_utc(_created)
            if (_created := getattr(model, "created_at", None))
            else None
        ),
        partial=any(s.provenance is Provenance.NOT_RECORDED for s in sections),
        dataset=dataset,
        leaderboard=leaderboard,
        winner=winner,
        baseline=baseline,
        drivers=drivers,
        reproducibility=reproducibility,
        caveats=_caveats(model, job),
    )


def _numeric_pairs(ranked: dict[Any, Any]) -> list[tuple[str, float]]:
    """Only the entries that are actually a name and a number."""
    out: list[tuple[str, float]] = []
    for key, value in ranked.items():
        try:
            number = float(value)
        except (TypeError, ValueError, ArithmeticError):
            continue
        # Same non-question as `_baseline` had: "did float() raise" lets NaN and
        # ±Infinity straight through (stdlib json.loads parses both as bare
        # literals), and a non-finite value here 500s the response on an owned
        # model. Ask whether it is a real number.
        if not math.isfinite(number):
            continue
        out.append((str(key), number))
    return out


def _flatten(text: str) -> str:
    """Collapse free text to one line before it enters the document.

    `MLModel.name` and `target_column` are user-supplied and are not newline-
    stripped anywhere upstream, so a name containing a newline injects structure
    into the exported Markdown — a heading or a list item the user never wrote.
    """
    return " ".join(str(text).split())


def _cell(text: str) -> str:
    """Escape a value for a Markdown table cell.

    Feature and column names come from uploaded CSV headers, which may legally
    contain `|` — unescaped, one such name silently breaks the table structure of
    the exported document.
    """
    return _flatten(str(text).replace("\\", "\\\\").replace("|", "\\|"))


def _code(text: str) -> str:
    """Wrap free text in an inline code span that its own backticks cannot close.

    `target_column` comes from an uploaded CSV header, where a backtick is legal.
    Markdown's own answer is a fence longer than the longest run inside, so the
    value survives verbatim rather than being mangled or stripped.
    """
    flat = _flatten(text)
    runs = [len(m) for m in re.findall(r"`+", flat)]
    fence = "`" * ((max(runs) if runs else 0) + 1)
    pad = " " if flat.startswith("`") or flat.endswith("`") else ""
    return f"{fence}{pad}{flat}{pad}{fence}"


def _or_dash(value: int | None) -> str:
    return "—" if value is None else str(value)


def _fmt(value: float | None, digits: int = 4) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _absent(section: Section) -> str:
    """Render a genuinely absent section.

    Only for `NOT_RECORDED`. A `STORED` section missing one optional field is not
    absent, and saying so is the mirror of the fabrication this module exists to
    prevent — see `_missing_field` below.
    """
    return f"_Not recorded._ {_flatten(section.note or '')}".strip()


def _missing_field(note: str | None) -> str:
    """Render one absent field inside a section whose data IS stored."""
    return f"_{_flatten(note or 'Not available for this model.')}_"


def render_markdown(report: ModelReport) -> str:
    """The canonical export. Rendered here, not in the browser, so it is one
    artifact the API and the UI agree on and pytest can assert against."""
    out: list[str] = [
        f"# Model report — {_flatten(report.model_name)}",
        "",
        f"- **Model id:** `{report.model_id}`",
        f"- **Problem type:** {report.problem_type}",
        f"- **Trained:** {report.trained_at.isoformat() if report.trained_at else '—'}",
        f"- **Report generated:** {report.generated_at.isoformat()}",
        "",
        "> Every figure below is either read from what the training run recorded, or "
        "computed here from stored data and labelled as such. Sections marked "
        "**Not recorded** were never captured — that is not the same as zero.",
        "",
        "## The data",
        "",
        f"- Target column: {_code(report.dataset.target_column)}",
        # `is None`, not `or`: a legitimate 0 is a fact, and rendering it as the
        # same em-dash used for absent values is exactly the mislabelling the
        # provenance design exists to prevent.
        f"- Training rows: {_or_dash(report.dataset.n_samples_train)}",
        f"- Features: {_or_dash(report.dataset.n_features)}",
        (
            "- Feature columns: "
            + ", ".join(_code(name) for name in report.dataset.feature_names)
            if report.dataset.feature_names
            else "- Feature columns: _Not recorded._"
        ),
        "",
        "## Algorithms tried",
        "",
    ]

    if report.leaderboard.rows:
        out += [
            "| Algorithm | CV score | Test score | Fit time (s) |",
            "|---|---|---|---|",
        ]
        for row in report.leaderboard.rows:
            mark = " **(winner)**" if row.is_winner else ""
            out.append(
                f"| {_cell(row.algorithm)}{mark} | {_fmt(row.cv_score)} | "
                f"{_fmt(row.test_score)} | {_fmt(row.training_time, 1)} |"
            )
    else:
        out.append(_absent(report.leaderboard))
    out.append("")

    out += ["## Baseline", ""]
    if report.baseline.score is not None:
        out += [
            f"A no-skill **{report.baseline.strategy}** predictor scores "
            f"**{_fmt(report.baseline.score)}** ({report.baseline.metric}) on the same "
            f"held-out rows.",
            "",
            f"_{_flatten(report.baseline.note or '')}_",
        ]
    else:
        out.append(_absent(report.baseline))
    out.append("")

    out += ["## Why this model", ""]
    out.append(
        f"**{_flatten(report.winner.algorithm)}** — CV {_fmt(report.winner.cv_score)}, "
        f"test {_fmt(report.winner.test_score)}."
    )
    out.append("")
    # Flattened like every other free text reaching the document. It is
    # LLM-free and deterministic today, but #795 scopes generated prose as a
    # later addition landing exactly here, and that would be user-influenced.
    out.append(
        _flatten(report.winner.explanation)
        if report.winner.explanation
        else _missing_field(report.winner.note)
    )
    # The stored metrics were on the wire from the first commit and rendered
    # nowhere, while the PR summary claimed them as covered. Someone defending a
    # prediction wants precision/recall/AUC, not only the headline CV score.
    extra = {
        k: v
        for k, v in (report.winner.metrics or {}).items()
        if k not in {"cv_score", "test_score", "training_time"}
        and isinstance(v, (int, float))
        and math.isfinite(float(v))
    }
    if extra:
        out += ["", "| Metric | Value |", "|---|---|"]
        out += [f"| {_cell(k)} | {_fmt(float(v))} |" for k, v in sorted(extra.items())]
    out.append("")

    out += ["## What drives it", ""]
    if report.drivers.features:
        source = _flatten(report.drivers.explainer_type or "stored importance")
        truncation = f" {_flatten(report.drivers.note)}" if report.drivers.note else ""
        out.append(f"Source: {source}.{truncation}")
        out.append("")
        out += ["| Feature | Importance |", "|---|---|"]
        out += [
            f"| {_cell(name)} | {_fmt(value)} |"
            for name, value in report.drivers.features
        ]
    else:
        out.append(_absent(report.drivers))
    out.append("")

    if report.caveats:
        out += ["## Caveats", ""]
        out += [f"- {_flatten(c)}" for c in report.caveats]
        out.append("")

    out += ["## Reproducibility", ""]
    if report.reproducibility.environment:
        out += ["| Component | Version |", "|---|---|"]
        out += [
            f"| {_cell(k)} | {_cell(v)} |"
            for k, v in sorted(report.reproducibility.environment.items())
        ]
    else:
        out.append(_absent(report.reproducibility))
    out += [
        "",
        "The random seed used for this run is **not recorded** by the platform, so "
        "this report does not state one.",
        "",
    ]
    return "\n".join(out)
