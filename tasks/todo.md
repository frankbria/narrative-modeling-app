# Issue #603: an automatic guard for text glued together in the server render

## Problem
A space between a JSX interpolation and the prose after it can vanish in the
server-rendered HTML while jsdom renders it correctly (#473: "Narrative Modeling
Appservice" on the Terms page). No component test can see it. The only guard is a
`curl | grep` in CLAUDE.md that someone has to remember to run.

## Plan
- [ ] `e2e/helpers/gluedText.ts::gluedBoundaries(html)`: every place two adjacent text
      nodes (React separates them with `<!-- -->`) meet with a word character on both
      sides, returned with the text around it.
- [ ] `e2e/workflows/glued-text.spec.ts` (@smoke): fetches the server-rendered HTML of
      every route under `app/` that has no dynamic segment, with the test user's cookies,
      and fails with each offending text. The legal pages must answer 200, so the check
      cannot pass by checking nothing.
- [ ] A test of the detector on known-glued HTML, so the guard has been seen to fail.
- [ ] Mutation check on the real stack: remove a `{' '}` from a legal page, run the spec,
      see it name the page and the text.
- [ ] CLAUDE.md: the manual command is now a spec.
