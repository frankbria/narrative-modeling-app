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
- [ ] 1. `refs` (3) — `components/training/TrainingProgress.tsx`
- [ ] 2. `static-components` (5) — Bar/Line/Scatter/FeatureImportance/ShapSummary charts
- [ ] 3. `preserve-manual-memoization` (1) — `lib/contexts/WorkflowContext.tsx`
- [ ] 4. `immutability` (28) — hoist function declarations above their effects
- [ ] 5. `set-state-in-effect` (26) — the behavioral group
- [ ] 6. Promote all five rules to `"error"`, delete the `react-compiler-rules-pending-burndown` block
- [ ] 7. Drop `--max-warnings` 297 → 234 (63 removed); keep the flag (234 non-compiler warnings remain, #333 debt)

## Invariants
- Frontend jest suite green before and after each group; `npx tsc --noEmit` clean.
- Never trust the aggregate — re-measure per-rule counts with the jq recipe from the issue.
- No behavior change beyond what each rule requires.
