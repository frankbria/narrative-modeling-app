# #859 — recipe browse and load use the routes the API has (P2.57)

Self-authored plan.

## Decisions made here
- The list and the load go through `lib/services/pipelineApi.ts`, like save, preview and
  apply since #855: `fetchRecipes(filter)`, `recipeListPath(filter)`, `recipeSteps(recipe)`.
  - all -> `GET /transformations/recipes` (the caller's and every public recipe)
  - mine -> `GET /transformations/recipes?include_public=false`
  - popular -> `GET /transformations/recipes/popular`
  The old call sent `filter` and `dataset_id`; no recipe route takes either.
- **Pinned to real responses.** A backend test saves a recipe through the route, reads
  both lists back, and writes the routes' query parameters and bodies to
  `__tests__/fixtures/recipeLists.json`. The frontend contract test checks each list
  request against it and builds a pipeline from the captured recipe.
- A failed list is shown in the browser as an alert. It used to keep the previous (empty)
  list and say nothing.
- `RecipeManager` was one component with every branch in it. It is now a shell over
  `RecipeBrowser` and `SaveRecipeForm`; `recipeFlow` turns steps into nodes and edges.
- The "Make this recipe public" box was not connected to anything. It now sends
  `is_public`, which is the only way a recipe reaches the Popular list from the UI.
- Lint warnings fell from 229 to 228 (an `any` went with the old component), so the cap
  is lowered to 228.

## Steps
- [x] Backend capture test and the fixture.
- [x] Failing jest: contract (routes, query parameters, steps from a real response) and
      the pipeline (list, each filter's route, load builds the pipeline, failure shown,
      public save).
- [x] The API functions, `recipeFlow`, the split components.
- [ ] Gate, cross-family review, PR, real-stack demo, CI, merge.
