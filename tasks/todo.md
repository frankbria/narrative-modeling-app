# #914 — three public handlers in authenticated routers, and a guard for the class (P1.71)

Self-authored plan (the issue has four acceptance criteria). Found in review of #512.

## Decisions made here
- `GET /transformations/available` and `GET /transformations/recipes/popular` take the
  session dependency. Both frontend callers already send the token.
- `GET /upload/test` is removed. Nothing calls it.
- **A recipe's `user_id` is returned to its owner only**, in every handler that can
  return another account's recipe: the popular list, the caller's own list (which
  includes public recipes) and a single public recipe. The issue names the popular list;
  the other two return the same field to any signed-in reader. One helper,
  `_recipe_response(recipe, viewer_id)`, builds the response for all three. The field
  becomes nullable; the frontend's only use of it is `recipe.user_id === currentUserId`.
- **The registry test walks the route table's dependency trees**, not the OpenAPI
  document: a route is authenticated when its dependant reaches `get_current_user_id`,
  `verify_api_key` or `require_admin`, including through router-level dependencies.
  Public routes are allow-listed by `module.function` with the reason, and the list
  fails when an entry stops existing or stops being public.
- `get_recipe` was cc 7, so its access check moves to `_require_readable`.

## Steps
- [x] Registry test; anonymous-request tests for the three routes.
- [x] Owner-id tests for the three recipe handlers.
- [x] The auth dependencies, the removal, `_recipe_response`; frontend type.
- [ ] CLAUDE.md, gate, cross-family review, PR, demo, CI, merge.
