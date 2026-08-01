# Issue #373 [P2.19] — Burn down React Compiler lint rules

**Plan source:** issue body + two enforcement comments. No architectural fork → autonomous.

Baseline (measured on `main` after `npm ci`): **297 total warnings, 63 React Compiler**.
Note: local `node_modules` was stale (eslint-config-next 15 / react-hooks 5 installed
against a package.json declaring 16) — `npm ci` was required before any count was real.

| Rule | Count | Fix shape |
|---|---|---|
| `react-hooks/immutability` | 28 | Effect calls a `const` arrow fn declared *below* it → hoist the declaration above the effect. Mechanical. |
| `react-hooks/set-state-in-effect` | 26 | Case-by-case: derive during render, reset via `key`, or move the set into the async continuation. |
| `react-hooks/static-components` | 5 | Recharts `CustomTooltip` defined inside the component body → lift to module scope, pass closed-over values as props. |
| `react-hooks/refs` | 3 | `ref.current = prop` during render (latest-ref pattern) → assign inside an effect. |
| `react-hooks/preserve-manual-memoization` | 1 | `WorkflowContext.tsx:241` — rework so the compiler can preserve the memo. |

## Order (smallest / lowest-risk first, one commit per group)
- [x] 1. `refs` (3) — `components/training/TrainingProgress.tsx`
- [x] 2. `static-components` (5) — Bar/Line/Scatter/FeatureImportance/ShapSummary charts
- [x] 3. `preserve-manual-memoization` (1) — same root cause as #4, cleared with it
- [x] 4. `immutability` (28) — hoist function declarations above their effects
- [ ] 5. `set-state-in-effect` — **split out to #393**. Not 26 but **46**: clearing
      `immutability` stopped the compiler bailing out of those components early,
      which surfaced 20 more. Every site is a loader doing `setLoading(true)`
      synchronously before its first `await`; fixing them means moving each
      spinner reset to the interaction that drives the refetch — a data-loading
      refactor across ~41 files with a per-site judgement call, not a lint edit.
- [x] 6. Promoted the four cleared rules to `"error"`; block stays for the one
      pending rule (#393 deletes it)
- [x] 7. `--max-warnings` 297 → **280** (17 removed). Verified exact: 280 exits 0,
      279 exits 1.

## Invariants
- Frontend jest suite green before and after each group; `npx tsc --noEmit` clean.
- Never trust the aggregate — re-measure per-rule counts with the jq recipe from the issue.
- No behavior change beyond what each rule requires.
