# Issue #532: remove tracked scratch and demo artifacts

## What the issue names, checked with `git ls-files` (AC1)
- `apps/backend/_demo_77.py`, `history-completed.png`, `model-ready.png`,
  `IMPLEMENTATION_PLANS_NEEDED.md`, `GITHUB_PROJECTS_GUIDE.md`: not tracked. No action
  beyond `.gitignore`.
- `coordination.md`, `memory-bank.md`: tracked. Empty claude-flow templates. Deleted.

## Also tracked and scratch (same categories)
- [x] `memory/agents/README.md`, `memory/sessions/README.md`: empty templates from the same commit.
- [x] `prompts/gh-75.txt`: a one-off prompt for a closed issue.
- [x] `sample_data.csv`: ten rows from 2025-04, referenced by nothing.
- [x] `tasks/issue-76-demo.md`, `apps/backend/tasks/`: per-issue demo notes and script.
- [x] `.beads/` runtime state: daemon lock and log (local paths), the SQLite database
      and journals, merge scratch. `issues.jsonl` and `metadata.json` stay.

## tasks/ (AC5)
Stays, holding only `todo.md` and `lessons.md`, which the issue workflow writes for
every issue. Everything else under it is ignored.

## Not in this change
- Root product documents (`BETA_ROADMAP.md`, `PRODUCT_REQUIREMENTS.md`, `USER_STORIES.md`)
  and the two 2025-12 feature guides: documentation drift is #535.
- `apps/backend/scripts/demo_*.py`, `apps/backend/docs/demos/`: kept where they are.
