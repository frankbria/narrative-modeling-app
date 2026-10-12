# Issue #609: the dataset-metering registry polices three prefixes

## Problem
`test_dataset_routes_are_metered.py` fails on any unclassified POST under
`/api/v1/upload`, `/api/v1/datasets` and `/api/v1/onboarding`. A dataset-creating route
mounted anywhere else is invisible to it. That already happened once: the onboarding
sample loader, found by a reviewer and fixed by adding its prefix.

## Plan
- [ ] A second scope beside the prefixes, keyed on what a handler does: an AST pass over
      `app/` finds every function that can reach the construction of `UserData` or
      `DatasetMetadata` (by call name, to a fixpoint), and every mounted write route on
      any prefix whose handler is one of them must be classified.
- [ ] The failure names the route, its handler and the chain of calls to the
      construction, with the three choices.
- [ ] Vacuity guards: the pass finds the known constructors, and finds every route in
      `_MUST_BE_METERED` (so it would have found each of them unlisted).
- [ ] Classify what it newly flags (17 routes): 15 reach `ensure_metadata_twin`, the twin
      of an upload already charged; 2 share a function name with one that does.
- [ ] The docstring states the new limit: matching is by name.
