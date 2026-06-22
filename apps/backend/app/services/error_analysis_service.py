"""Error-analysis engine for trained models (issue #81).

Analyzes a model's held-out predictions to surface *where* and *why* it fails:
error distribution, commonly-confused class pairs, high-error feature segments,
clusters of similar errors, decision-tree error patterns, and a browsable list
of error cases. Plus AI improvement suggestions (OpenAI with a deterministic
rule-based fallback, mirroring ``EvaluationExplanationService``).

Reuses the held-out arrays persisted at training time (issue #79) plus the
held-out transformed feature matrix added to the same payload for #81. The
analysis works in **engineered-feature space** (same as SHAP, #80); there is no
original-space reconstruction.

The service is stateless and **never raises**: each section degrades to an empty
result on any failure so the endpoint always returns a usable response.
"""

import asyncio
import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
from openai import OpenAI, OpenAIError

from app.schemas.error_analysis import (
    ConfusionPair,
    ErrorCase,
    ErrorCluster,
    ErrorDistribution,
    ErrorPattern,
    ErrorSegment,
)
from app.utils.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)

DEFAULT_MAX_CASES = 200
MAX_SEGMENTS = 12
MAX_PATTERNS = 8
MAX_CONFUSION_PAIRS = 10
MIN_CLUSTER_ERRORS = 10
MAX_TOP_FEATURES_PER_CASE = 12
# Regression: a "large error" is a residual beyond one standard deviation of the
# held-out residuals. ponytail: simple, interpretable threshold; swap for a
# configurable percentile if users need finer control.
REGRESSION_ERROR_SIGMA = 1.0


@dataclass
class ErrorAnalysisData:
    """Computed error-analysis components (the route wraps these in the schema)."""

    distribution: ErrorDistribution | None = None
    confusion_pairs: list[ConfusionPair] = field(default_factory=list)
    segments: list[ErrorSegment] = field(default_factory=list)
    clusters: list[ErrorCluster] = field(default_factory=list)
    patterns: list[ErrorPattern] = field(default_factory=list)
    cases: list[ErrorCase] = field(default_factory=list)
    has_feature_matrix: bool = False


def _as_str_array(values: Any) -> np.ndarray:
    return np.asarray([str(v) for v in values])


def _sanitize(value: str, max_len: int = 200) -> str:
    """Strip control chars and cap length before a user-controlled string (a
    feature name, class label, or algorithm) reaches the OpenAI prompt or a
    user-facing suggestion — a light defense against prompt injection."""
    cleaned = "".join(ch for ch in str(value) if ch == " " or ch.isprintable())
    return cleaned[:max_len]


def _feature_matrix(
    x_test: Any, feature_names: list[str] | None
) -> tuple[np.ndarray | None, list[str]]:
    """Coerce persisted X_test rows into a numeric 2D array, or (None, [])."""
    if x_test is None or not feature_names:
        return None, []
    try:
        arr = np.asarray(x_test, dtype=float)
    except (ValueError, TypeError):
        return None, []
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] != len(feature_names):
        return None, []
    # Non-finite cells (the #79 payload maps NaN/inf -> None -> nan here) break
    # sklearn; replace with column means so analysis still runs.
    if not np.all(np.isfinite(arr)):
        col_means = np.nanmean(np.where(np.isfinite(arr), arr, np.nan), axis=0)
        col_means = np.where(np.isfinite(col_means), col_means, 0.0)
        inds = np.where(~np.isfinite(arr))
        arr[inds] = np.take(col_means, inds[1])
    return arr, list(feature_names)


class ErrorAnalysisService:
    """Compute error analysis + AI suggestions for a trained model."""

    def __init__(self) -> None:
        # None-safe when OPENAI_API_KEY is unset — suggestions use the
        # rule-based fallback (mirrors EvaluationExplanationService).
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

    # ------------------------------------------------------------------ #
    # Core analysis (pure compute, never raises)
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        *,
        problem_type: str,
        y_test: Any,
        y_pred: Any,
        y_proba: Any | None,
        class_labels: list[str] | None,
        x_test: Any | None,
        feature_names: list[str] | None,
        max_cases: int = DEFAULT_MAX_CASES,
    ) -> ErrorAnalysisData:
        """Run every analysis section, each guarded so one failure can't sink the rest."""
        is_classification = "regress" not in (problem_type or "").lower()
        yt = np.asarray(y_test)
        yp = np.asarray(y_pred)
        n = min(len(yt), len(yp))
        yt, yp = yt[:n], yp[:n]

        errors = self._error_indicator(is_classification, yt, yp)
        x_arr, feat_names = _feature_matrix(x_test, feature_names)
        # X_test must align row-for-row with the y arrays; a mismatched length
        # (truncated/corrupted artifact) would silently misalign every
        # feature-based section, so degrade to no matrix instead.
        if x_arr is not None and x_arr.shape[0] != n:
            x_arr, feat_names = None, []

        data = ErrorAnalysisData(has_feature_matrix=x_arr is not None)
        data.distribution = self._safe(
            "distribution", self._distribution, is_classification, yt, yp, errors
        )
        if is_classification:
            data.confusion_pairs = self._safe(
                "confusion_pairs", self._confusion_pairs, yt, yp, class_labels
            ) or []
        if x_arr is not None:
            data.segments = self._safe(
                "segments", self._segments, x_arr, feat_names, errors
            ) or []
            data.clusters = self._safe(
                "clusters", self._clusters, x_arr, feat_names, errors, yt, yp,
                is_classification,
            ) or []
            data.patterns = self._safe(
                "patterns", self._patterns, x_arr, feat_names, errors
            ) or []
        data.cases = self._safe(
            "cases", self._cases, yt, yp, y_proba, errors, x_arr, feat_names,
            is_classification, max_cases,
        ) or []
        return data

    @staticmethod
    def _error_indicator(
        is_classification: bool, yt: np.ndarray, yp: np.ndarray
    ) -> np.ndarray:
        if is_classification:
            return _as_str_array(yt) != _as_str_array(yp)
        resid = np.asarray(yp, dtype=float) - np.asarray(yt, dtype=float)
        std = float(np.std(resid))
        if std == 0:
            # Constant residual: all-zero → no errors; constant nonzero bias
            # (e.g. every prediction off by +10) → every row is an error.
            return np.abs(resid) > 0
        return np.abs(resid) > REGRESSION_ERROR_SIGMA * std

    def _safe(self, name: str, fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except Exception as exc:  # never raises — degrade this section only
            logger.warning(f"Error-analysis section '{name}' failed: {exc}")
            return None

    # ------------------------------------------------------------------ #
    # Sections
    # ------------------------------------------------------------------ #
    @staticmethod
    def _distribution(
        is_classification: bool, yt: np.ndarray, yp: np.ndarray, errors: np.ndarray
    ) -> ErrorDistribution:
        total = int(len(yt))
        n_err = int(errors.sum())
        per_class: dict[str, float] = {}
        if is_classification:
            yt_s = _as_str_array(yt)
            for label in sorted(set(yt_s)):
                mask = yt_s == label
                support = int(mask.sum())
                if support:
                    per_class[label] = round(float(errors[mask].sum()) / support, 4)
        return ErrorDistribution(
            total_samples=total,
            total_errors=n_err,
            overall_error_rate=round(n_err / total, 4) if total else 0.0,
            per_class_error_rate=per_class,
        )

    @staticmethod
    def _confusion_pairs(
        yt: np.ndarray, yp: np.ndarray, class_labels: list[str] | None
    ) -> list[ConfusionPair]:
        yt_s = _as_str_array(yt)
        yp_s = _as_str_array(yp)
        support = Counter(yt_s.tolist())
        pair_counts = Counter(
            (a, p) for a, p in zip(yt_s.tolist(), yp_s.tolist()) if a != p
        )
        pairs = [
            ConfusionPair(
                actual=a,
                predicted=p,
                count=int(c),
                rate=round(c / support[a], 4) if support[a] else 0.0,
            )
            for (a, p), c in pair_counts.most_common(MAX_CONFUSION_PAIRS)
        ]
        return pairs

    @staticmethod
    def _segments(
        x_arr: np.ndarray, feat_names: list[str], errors: np.ndarray
    ) -> list[ErrorSegment]:
        n = len(errors)
        overall = float(errors.mean()) if n else 0.0
        min_samples = max(5, int(0.02 * n))
        out: list[ErrorSegment] = []
        for j, name in enumerate(feat_names):
            col = x_arr[:, j]
            edges = np.unique(np.quantile(col, [0.0, 0.25, 0.5, 0.75, 1.0]))
            if len(edges) < 2:
                continue
            for k in range(len(edges) - 1):
                lo, hi = float(edges[k]), float(edges[k + 1])
                last = k == len(edges) - 2
                mask = (col >= lo) & (col <= hi if last else col < hi)
                cnt = int(mask.sum())
                if cnt < min_samples:
                    continue
                rate = float(errors[mask].mean())
                if rate > overall:
                    out.append(
                        ErrorSegment(
                            feature=name,
                            range_label=f"{name} in [{lo:.2f}, {hi:.2f}{']' if last else ')'}",
                            lower=lo,
                            upper=hi,
                            error_rate=round(rate, 4),
                            error_count=int(errors[mask].sum()),
                            sample_count=cnt,
                        )
                    )
        out.sort(key=lambda s: s.error_rate, reverse=True)
        return out[:MAX_SEGMENTS]

    @staticmethod
    def _clusters(
        x_arr: np.ndarray,
        feat_names: list[str],
        errors: np.ndarray,
        yt: np.ndarray,
        yp: np.ndarray,
        is_classification: bool,
    ) -> list[ErrorCluster]:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        err_idx = np.where(errors)[0]
        if len(err_idx) < MIN_CLUSTER_ERRORS:
            return []
        x_err = x_arr[err_idx]
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x_err)
        k = min(5, max(2, len(err_idx) // 25))
        if k >= len(err_idx):
            return []
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(x_scaled)

        overall_mean = x_arr.mean(axis=0)
        overall_std = x_arr.std(axis=0)
        yt_s = _as_str_array(yt)
        yp_s = _as_str_array(yp)
        clusters: list[ErrorCluster] = []
        for cid in range(k):
            members = err_idx[labels == cid]
            if len(members) == 0:
                continue
            cmean = x_arr[members].mean(axis=0)
            z = np.where(overall_std > 0, (cmean - overall_mean) / overall_std, 0.0)
            order = np.argsort(-np.abs(z))
            traits = [
                f"{'high' if z[j] > 0 else 'low'} {feat_names[j]}"
                for j in order[:3]
                if abs(z[j]) >= 0.5
            ]
            dominant = None
            if is_classification:
                pair_counts = Counter(
                    f"{yt_s[i]}→{yp_s[i]}" for i in members
                )
                if pair_counts:
                    dominant = pair_counts.most_common(1)[0][0]
            clusters.append(
                ErrorCluster(
                    cluster_id=int(cid),
                    size=int(len(members)),
                    characteristics=traits,
                    dominant_confusion=dominant,
                )
            )
        clusters.sort(key=lambda c: c.size, reverse=True)
        return clusters

    @staticmethod
    def _patterns(
        x_arr: np.ndarray, feat_names: list[str], errors: np.ndarray
    ) -> list[ErrorPattern]:
        from sklearn.tree import DecisionTreeClassifier

        y = errors.astype(int)
        if len(np.unique(y)) < 2:  # need both errors and non-errors
            return []
        n = len(y)
        overall = float(y.mean())
        min_samples = max(5, int(0.02 * n))
        tree = DecisionTreeClassifier(
            max_depth=3, min_samples_leaf=min_samples, random_state=42
        ).fit(x_arr, y)
        t = tree.tree_
        classes = list(tree.classes_)
        err_col = classes.index(1) if 1 in classes else None
        if err_col is None:
            return []
        out: list[ErrorPattern] = []

        def walk(node: int, conditions: list[str]) -> None:
            left, right = t.children_left[node], t.children_right[node]
            if left == right:  # leaf
                # tree_.value holds per-class PROPORTIONS (sklearn >=1.4; target
                # is 1.7) not counts; use n_node_samples for the sample count
                # and derive the error count from the proportion.
                samples = int(t.n_node_samples[node])
                rate = float(t.value[node][0][err_col])
                err_count = int(round(rate * samples))
                if samples >= min_samples and rate > overall and conditions:
                    out.append(
                        ErrorPattern(
                            rule=" AND ".join(conditions),
                            error_rate=round(rate, 4),
                            error_count=err_count,
                            sample_count=samples,
                        )
                    )
                return
            feat = feat_names[t.feature[node]]
            thr = float(t.threshold[node])
            walk(left, conditions + [f"{feat} <= {thr:.2f}"])
            walk(right, conditions + [f"{feat} > {thr:.2f}"])

        walk(0, [])
        out.sort(key=lambda p: p.error_rate, reverse=True)
        return out[:MAX_PATTERNS]

    @staticmethod
    def _cases(
        yt: np.ndarray,
        yp: np.ndarray,
        y_proba: Any | None,
        errors: np.ndarray,
        x_arr: np.ndarray | None,
        feat_names: list[str],
        is_classification: bool,
        max_cases: int,
    ) -> list[ErrorCase]:
        proba = None
        if y_proba is not None:
            try:
                proba = np.asarray(y_proba, dtype=float)
            except (ValueError, TypeError):
                proba = None
        all_err = np.where(errors)[0]
        if is_classification and len(all_err) > max_cases:
            # Round-robin across confusion-pair groups so every reported pair
            # keeps at least some cases — otherwise a first-N-by-index cap could
            # drop all examples of a pair that the dashboard still ranks, and
            # clicking it (client-side drill-down) would show nothing.
            yt_s = _as_str_array(yt)
            yp_s = _as_str_array(yp)
            groups: dict[tuple[str, str], list[int]] = {}
            for idx in all_err:
                groups.setdefault((yt_s[idx], yp_s[idx]), []).append(int(idx))
            ordered = sorted(groups.values(), key=len, reverse=True)
            selected: list[int] = []
            pos = 0
            while len(selected) < max_cases and any(pos < len(g) for g in ordered):
                for g in ordered:
                    if pos < len(g):
                        selected.append(g[pos])
                        if len(selected) >= max_cases:
                            break
                pos += 1
            err_idx = np.array(sorted(selected))
        else:
            err_idx = all_err[:max_cases]
        show = feat_names[:MAX_TOP_FEATURES_PER_CASE]
        cases: list[ErrorCase] = []
        for i in err_idx:
            confidence = None
            if proba is not None and i < len(proba):
                row = proba[i]
                if np.all(np.isfinite(row)):
                    confidence = round(float(np.max(row)), 4)
            top: dict[str, float] = {}
            if x_arr is not None:
                top = {
                    name: round(float(x_arr[i, j]), 4) for j, name in enumerate(show)
                }
            cases.append(
                ErrorCase(
                    index=int(i),
                    actual=str(yt[i]),
                    predicted=str(yp[i]),
                    confidence=confidence,
                    top_features=top,
                )
            )
        return cases

    # ------------------------------------------------------------------ #
    # AI suggestions (OpenAI with rule-based fallback) — never raises
    # ------------------------------------------------------------------ #
    async def generate_suggestions(
        self,
        data: ErrorAnalysisData,
        *,
        problem_type: str,
        algorithm: str | None,
    ) -> tuple[list[str], str]:
        """Return ``(suggestions, generated_by)`` where generated_by is openai|fallback."""
        context = self._suggestion_context(data, problem_type, algorithm)
        if self.client is not None:
            try:
                suggestions = await self._openai_suggestions(context)
            except Exception as exc:
                # Includes CircuitBreakerOpen; catching here (not inside the
                # breaker-wrapped method) preserves the breaker's failure count.
                logger.warning(
                    f"OpenAI error suggestions unavailable, using fallback: {exc}"
                )
                suggestions = None
            if suggestions:
                return suggestions, "openai"
        return self._fallback_suggestions(context), "fallback"

    @staticmethod
    def _suggestion_context(
        data: ErrorAnalysisData, problem_type: str, algorithm: str | None
    ) -> dict[str, Any]:
        dist = data.distribution
        return {
            "problem_type": _sanitize(problem_type),
            "algorithm": _sanitize(algorithm or "the selected algorithm"),
            "overall_error_rate": dist.overall_error_rate if dist else None,
            "total_errors": dist.total_errors if dist else 0,
            "worst_classes": (
                [
                    (_sanitize(label), rate)
                    for label, rate in sorted(
                        (dist.per_class_error_rate or {}).items(),
                        key=lambda kv: kv[1],
                        reverse=True,
                    )[:3]
                ]
                if dist
                else []
            ),
            "top_confusion_pairs": [
                (_sanitize(p.actual), _sanitize(p.predicted), p.count)
                for p in data.confusion_pairs[:3]
            ],
            "top_segments": [
                (_sanitize(s.range_label), s.error_rate) for s in data.segments[:3]
            ],
            "top_patterns": [
                (_sanitize(p.rule), p.error_rate) for p in data.patterns[:3]
            ],
        }

    @staticmethod
    def _fallback_suggestions(context: dict[str, Any]) -> list[str]:
        out: list[str] = []
        rate = context.get("overall_error_rate")
        if rate is not None and rate > 0.25:
            out.append(
                f"Overall error rate is high ({rate:.0%}). Collect more training "
                "data or revisit feature engineering before relying on predictions."
            )
        for actual, predicted, count in context.get("top_confusion_pairs", []):
            out.append(
                f"The model confuses '{actual}' with '{predicted}' ({count} cases). "
                f"Add features that distinguish these two classes."
            )
        for label, err_rate in context.get("worst_classes", []):
            if err_rate >= 0.5:
                out.append(
                    f"Class '{label}' is wrong {err_rate:.0%} of the time — it may be "
                    "under-represented; consider gathering more examples of it."
                )
        for range_label, err_rate in context.get("top_segments", []):
            out.append(
                f"Errors concentrate where {range_label} ({err_rate:.0%} error rate); "
                "inspect this region for data-quality or labeling issues."
            )
        for rule, err_rate in context.get("top_patterns", []):
            out.append(
                f"A pattern of high error ({err_rate:.0%}) occurs when {rule}; "
                "engineering features for this region may help."
            )
        if not out:
            out.append(
                "Errors are spread evenly with no dominant pattern. Broadly improving "
                "data quality or trying a different algorithm is the best next step."
            )
        return out[:8]

    @with_circuit_breaker(
        "openai",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        # OpenAIError only: a parse error on a successful response must not open
        # the circuit (the caller still routes it to the rule-based fallback).
        exceptions=(OpenAIError,),
        fallback_value=None,
    )
    async def _openai_suggestions(self, context: dict[str, Any]) -> list[str] | None:
        """Call OpenAI in JSON mode; exceptions propagate for the breaker.

        Only called when ``self.client`` is set (guarded by the caller).
        """
        # The OpenAI client is effectively dynamically typed here; cast keeps
        # mypy from resolving the overloaded create() against literal kwargs.
        client = cast(Any, self.client)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an ML advisor. Given a model's error analysis, "
                        "return concise, actionable suggestions to reduce errors. "
                        'Respond as JSON: {"suggestions": ["...", "..."]}.'
                    ),
                },
                {"role": "user", "content": json.dumps(context)},
            ],
            temperature=0.4,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return [str(s) for s in (data.get("suggestions") or [])][:8]


error_analysis_service = ErrorAnalysisService()
