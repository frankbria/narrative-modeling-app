# Issue #102 — Data quality scoring system (P5.10, post-beta V2)

**Lean adaptation.** The CodeRabbit plan was heavily over-scoped (new `QualityGate`
Beanie model + CRUD + presets, a `QualityReportGenerator` with PDF export, a separate
`ActionableRecommendation` model + a *new* `ISSUE_TO_TRANSFORMATION_MAP` that duplicates
the existing `FixSuggestionEngine`, configurable per-request dimension weights, 6 new
frontend components + a new page + new API client/hooks). This plan builds **on the real
surfaces** that already exist and cuts the gold-plating.

## Ground truth (verified in code)
- `QualityAssessmentService.assess_quality()` already computes 0-1 dimension scores for
  completeness / consistency / validity / uniqueness (accuracy = validity placeholder,
  timeliness = 1.0 placeholder) and text `recommendations`. Returns `QualityReport`.
- `GET /api/v1/data/{file_id}/quality` returns the cached `UserData.quality_report`.
- `TransformationLineage` (`app/models/version.py`) already has
  `quality_before/quality_after/quality_improvement` fields — **declared but never
  populated** (dead). `DatasetVersion` is real and created on transformation.
- `transformation_service.py` (~L406) has BOTH `df` (before) and `transformed_df` (after)
  in hand at the exact call to `versioning_service.create_transformation_version()`.
- `TransformationType` enum (`app/models/transformation.py`) is the canonical transform list.
- Frontend already has `QualityReportCard.tsx` (rendered in `/explore/[id]` Quality tab),
  a `LineChart.tsx` Recharts wrapper, and quality types in `lib/types/api.ts`.

## Acceptance criteria
- [x] AC1: Overall quality score (0-100) combining completeness, validity, consistency,
      uniqueness, accuracy — `score_0_100` + `component_scores` on `QualityReport`
- [x] AC2: Quality improvement recommendations tied to existing transformation tooling —
      `actionable_recommendations` mapping issues → canonical `TransformationType`
- [x] AC3: Quality trend tracking across dataset versions — lineage `quality_*` populated +
      `GET /datasets/{id}/quality-trend`
- [x] AC4: Optional quality gates for workflow progression — `quality_gate_service` (soft)
- [x] AC5: Quality report generation + frontend dashboard —
      `GET /data/{id}/quality-report` + `QualityDashboard` on the explore Quality tab

## Bug fixed in passing (blocked AC3)
- `TransformationStep(**step)` in `_create_lineage` received `transformation_type`-keyed dicts
  (wrong field name) and the `step_type` validator only allowed 8 of the 39 `TransformationType`
  values → `ValidationError` (a `ValueError`) swallowed into an `OperationError`, so **every
  transform on a dataset with a base version failed**. Fixed: correct dict field names in
  `transformation_service` + validator now accepts all `TransformationType` values.

## Plan

### Step 1 — 0-100 score + component scores + actionable recommendations (AC1, AC2)
`app/services/data_processing/quality_assessment.py`
- Add `score_0_100: float` and `component_scores: dict[str, float]` (0-100, the 5 AC
  dimensions; exclude the timeliness placeholder) to `QualityReport`, computed equal-weight
  from existing `dimension_scores`. **No configurable weights** (not in AC; equal weight is
  the existing behaviour — keeps backward-compat, no query param).
- Add an `actionable_recommendations: list[ActionableRecommendation]` field: small struct
  `{dimension, description, transformation_type, affected_columns, severity}` mapping each
  quality dimension's issues to a canonical `TransformationType` (completeness→`fill_missing`,
  consistency-casing→`fix_casing`, consistency-numeric→`to_numeric`,
  consistency-date→`to_datetime`, validity-outlier→`outlier_removal`,
  uniqueness→`remove_duplicates`). Reuse existing per-issue `affected columns`. Keep the
  existing text `recommendations` unchanged (backward-compat).
- Tests: extend `tests/test_processing/test_quality_assessment.py`.

### Step 2 — Populate quality lineage during transformation (AC3)
`app/services/versioning_service.py` + `app/services/transformation_service.py`
- Add optional `quality_before: dict | None`, `quality_after: dict | None` params to
  `create_transformation_version()` and `_create_lineage()`; when present, set
  `lineage.quality_before/after` and `quality_improvement = after.score_0_100 -
  before.score_0_100`. Never fail the transform on a quality error (best-effort).
- In `transformation_service.py` compute quality on `df` and `transformed_df` (derive a
  simple column-type map from dtypes) and pass both in.
- Tests: `tests/test_services/` lineage-quality population (real flow).

### Step 3 — Quality trend endpoint (AC3)
`app/api/routes/versions.py`
- `GET /api/v1/datasets/{dataset_id}/quality-trend` (owner-scoped, 404 unknown/foreign):
  read lineage records for the dataset ordered by version, return per-version
  `{version_number, created_at, score_before, score_after, improvement, transformation}`
  plus overall improvement since v1. Empty/no-versions → empty trend (never 500).
- Tests: `tests/test_api/`.

### Step 4 — Soft quality gates + report endpoint (AC4, AC5 backend)
- `app/services/quality_gate_service.py` (stateless, no DB model): `evaluate(report)` with
  default thresholds (ML-ready: overall ≥70, completeness ≥80, validity ≥70) → list of
  `{gate_name, passed, actual_score, required_score, failing_dimensions, is_blocking:false}`.
  **No `QualityGate` Beanie model, no CRUD, no presets persistence** — soft/advisory only.
- `GET /api/v1/data/{file_id}/quality-report` aggregates: `score_0_100`, component scores,
  actionable recommendations, gate results, and trend (if the dataset has versions). JSON
  only — **no PDF** (not in AC; defer).
- Tests: `tests/test_services/` + `tests/test_api/`.

### Step 5 — Frontend quality dashboard (AC5 frontend) — IN SCOPE (user chose lean dashboard)
`lib/services/quality.ts` (typed client for the report + trend endpoints) +
a dashboard surface reusing the existing `QualityReportCard` with a 0-100 gauge, the
existing `LineChart` for the trend, an actionable-recommendations list, and gate status.
Mirror types in `lib/types/`. Component tests under `__tests__/`.

## Deviations from CodeRabbit plan (why)
- Drop configurable dimension weights / `weights` query param — not in AC, equal weight is
  current behaviour. (YAGNI)
- Drop the new `ActionableRecommendation` *model file* + `ISSUE_TO_TRANSFORMATION_MAP`
  constant — fold a tiny dimension→`TransformationType` map into the service; reuse the
  canonical enum instead of duplicating the existing `FixSuggestionEngine` mapping.
- Drop `QualityGate` Beanie model + `QualityGateService` CRUD + presets — soft gates are a
  stateless evaluator with default thresholds.
- Drop PDF export from report generation — JSON only (not in AC).
- Drop base-version quality backfill / new `initial_quality` field — trend's first
  `quality_before` already captures the base-version quality.

## Test commands
- Backend: `cd apps/backend && uv run pytest tests/test_processing/test_quality_assessment.py tests/test_services/ tests/test_api/ -k quality -v`
- Frontend: `cd apps/frontend && npm test` + `npm run type-check`
