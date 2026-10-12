# #860 — Export Code is a route that returns a script that runs (P2.58)

Self-authored plan. The issue offers two ways out: implement the route, or remove the
button. Implemented.

## Why implement
- Half of it existed: `POST /recipes/{id}/export` already returned Python for a saved
  recipe, from a hand-written generator that covered three of the engine's four types and
  emitted nothing for `drop_missing` or for a fill with no column named. Removing the
  button would have left that wrong script in the API.
- A script the user can run on their own machine is the one thing the pipeline gives
  that outlives the app.

## Decisions made here
- **The generator lives with the engine.** `BaseTransformation.code()` is abstract; each
  of the four classes writes its statements beside its `apply`. `code_export.pipeline_script`
  composes them into a module with `transform(df)` and a command line.
- **Held equal by execution.** The test runs the generated script and the engine on the
  same frame for 19 parameter cases, a four-step pipeline and every registered type, and
  compares the frames.
- **Parameters are data.** Everything from the request is written with `repr`. A test
  feeds a column name that reads as code and gets the same frame as the engine.
- A step the engine cannot run, or with invalid parameters, is a 422 naming the step
  ("Step 2 (fill_missing): …"), for the pipeline and for a saved recipe.
- `ffill` / `bfill` are emitted as the method calls, since `fillna(method=…)` is
  deprecated and gone in pandas 3; the result is the same.
- The script does not repeat the engine's refusal of a drop that removes more than half
  the rows; the generated step says so in a comment.
- The response is JSON (`language`, `filename`, `code`), so the request and response can
  be pinned like the rest; the frontend makes the download.

## Steps
- [x] Parity tests, then `code()` on the four classes and `pipeline_script`.
- [x] The route, its tests, the recipe export reusing it.
- [x] Frontend: `exportRequest` in the contract fixture, the download, the failure shown.
- [x] Real-stack: the Prepare smoke test downloads the script.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
