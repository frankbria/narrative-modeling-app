# Issues #571, #576, #577: the GLM review workflow

One file, three issues, one PR.

## #571 AC3: a reviewer that never started must not look like a clean review
A `startup_failure` creates no job, so nothing inside the reviewer's workflow can
report it. A second workflow has to look from outside.
- [ ] `scripts/ci/review_bots_health.sh`: for each reviewer workflow, the newest runs;
      if the latest one that ran ended in `startup_failure`, open (or comment on) an alert
      issue; otherwise close an open alert. `--dry-run`, and `--self-check` with a case table.
- [ ] `.github/workflows/review-bots-health.yml`: every 6 hours and on dispatch.
- [ ] CI runs the self-check; a test pins the workflow's permissions and the dedupe phrase.

## #576: the size gate
- [ ] Drop it. Every human-authored PR that is not docs-only is reviewed (`paths-ignore`
      already skips the docs-only ones). A small diff is a short, cheap review, and the
      one PR the gate skipped was a credential redaction.

## #577: comment archaeology
- [ ] Keep the two invariants as rules (no caller-level `concurrency:`; `permissions:`
      at least what the pinned callee declares). Drop run ids, cross-repo issue numbers
      and comparisons with other repos.

## Then
- [ ] CLAUDE.md, actionlint, shellcheck, review, demo (dry run against the real API), PR.
- [ ] After merge: dispatch the new workflow once and read its run.
