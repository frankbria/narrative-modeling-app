# Issue #188: claude-review workflow malfunctioned on PR #187 (55-min hang + ~30 junk comments)

> Previous plan (issue #76 — training progress monitoring) was **completed** and merged in PR #187
> (commit c9c9553); see `git log tasks/todo.md`.

Plan source: CodeRabbit comment on issue #188, adapted to codebase findings.

## Adapted Plan

### Step 1: Add runaway-execution safeguards to `claude-code-review.yml`
- File: `.github/workflows/claude-code-review.yml`
- Add `timeout-minutes: 10` at the job level (`claude-review` job) — matches the lower end of existing CI timeouts (ci.yml uses 10–30) and is ~3x the normal ~3.5-min run
- Add `--max-turns 20` to the existing `claude_args` (the action's v1 API has **no** `max_turns` input; `claude_args` passes CLI flags directly — verified against `anthropics/claude-code-action` action.yml)

### Step 2: Rewrite the review prompt to prevent content dumping
- File: `.github/workflows/claude-code-review.yml` (`prompt` field)
- Frame CLAUDE.md as reference-only context ("do not include its content in your output")
- Explicit output format: a SINGLE consolidated review comment containing only findings, organized by category
- Negative instruction: do not echo reference files, test fragments, or debugging output; do not post test/partial comments
- Keep existing `claude_args` tool restrictions unchanged

### Step 3: Apply safeguards to `claude.yml` (@claude mention workflow)
- File: `.github/workflows/claude.yml`
- Add `timeout-minutes: 30` at the job level (interactive @claude tasks can legitimately run longer than reviews)
- Add `claude_args: '--max-turns 50'`

### Step 4: Delete junk comments on PR #187 (operational, after plan approval)
- 33 `github-actions[bot]` comments posted 07:45:10–08:01:11 UTC on 2026-06-11 (IDs inventoried: 4678321812 … 4678444015)
- Preserve frankbria's "Final Triage Summary" comment (id 4678449782) — it captures the two substantive findings
- Delete via `gh api -X DELETE /repos/.../issues/comments/{id}`; document deleted IDs in an issue #188 comment for audit

## Acceptance Criteria
- [x] `claude-review` job self-terminates via `timeout-minutes: 10`
- [x] Agent turn limit configured via `claude_args --max-turns` (design choice resolved: no native input)
- [x] Review prompt separates reference context from output; single consolidated comment mandated; anti-dumping instruction present
- [x] `claude.yml` has equivalent safeguards
- [x] PR #187 junk comments deleted; Final Triage Summary preserved; deleted IDs documented on issue #188

## Test/Validation Strategy
- YAML workflows have no unit tests — validate with `actionlint` (or yamllint fallback) + CI green
- Demo: show diffs with timeouts/max-turns/prompt, show PR #187 comment list cleaned (bot junk gone, triage summary intact)

## Deviations from Original Plan
- Design Choice 1 resolved concretely: `max_turns` is not an action input in v1; using `claude_args: '--max-turns N'` instead (documented migration path)
- Skipping step-level `timeout-minutes` (job-level is sufficient; step-level adds noise for no extra safety here)
- claude.yml gets a higher budget (30 min / 50 turns) than the review job since @claude tasks are open-ended
- Junk window extended to 08:01:11 UTC — four more bot junk comments ("✅", "✅ test", "test—more", "world") landed just after 07:59 from the same run
