# Issue #674: deploy_model saves the whole document

## Problem
`PUT /ml/{id}/deploy` reads the model, sets four fields in memory and calls `save()`,
which writes every field back from that copy. A `last_used_at` stamped by a prediction
in between (a targeted `$set`, #725) is reverted. `PUT /ml/{id}/deactivate` does the same.

## Plan
- [x] RED: a stamp written after the handler's read survives the request, for both routes,
      against real documents.
- [x] Both handlers write only their own fields with `model.set({...})`.
- [x] The mock-based deactivate test asserted an in-memory flag; it now asserts the write.
