# #898 — a failure reported in a 200 deletes the file it uploaded (P2.61)

Self-authored plan.

## Decisions made here
- **A decorator, not a call in each failure branch.** `@discards_uploads_on_reported_failure`
  wraps the route and, when the answer's `success` is false, runs the middleware's own
  ownership lookup over what the request uploaded. Every one of these routes already
  answers with a `success` field. A decorator covers the failure branches a handler has
  today and the next one added, and the handlers (three of them far over the complexity
  ceiling) are not edited.
- `discard_unowned_uploads()` is the call underneath, as the issue asks for.
- **The lookup decides, not the report.** A fix that half-worked, or a failure after the
  dataset moved, leaves a row naming the file; it is kept. Tested.
- **The bulk job keeps its own record.** It runs after its request has answered, so it
  starts a list of its own and discards from it when the job fails. That also stops the
  job's file landing in the request's list.
- Auto-clean and recipe apply call the pipeline route in-process, so they are covered
  through it. Tested for auto-clean.

## Steps
- [x] Unit tests on a small app: failure in a 200 deletes; success, and an answer with
      no `success` field, keep; an owned object is kept; the signature FastAPI reads is
      unchanged; outside a request nothing happens; a job's own list.
- [x] Route tests on real documents with a recorded put: apply, pipeline, auto-clean,
      data-issue fix and batch, feature apply, the bulk job; the success path of each.
      With the decorators removed, seven fail.
- [x] LocalStack: the real bucket is empty of `transformed/` files after each forced
      failure (apply, pipeline, both fix routes, the bulk job), and a successful apply
      keeps its file.
- [x] CLAUDE.md.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
