# #512 — the published API surface describes what exists (P2.16)

Self-authored plan (the issue has four acceptance criteria).

## Decisions made here
- **The hand-written SDK surface is deleted**: `/docs/clients/{language}`,
  `/docs/integrations/{framework}`, `/docs/postman` and the 800 lines that produced
  them. They described endpoints that do not exist (`/models/train`, `/data/upload`),
  nothing in the frontend calls them, and a second, real SDK already exists: the
  per-model one (`/ml/{id}/sdk`, #86), generated for a deployment against its actual
  serving URL. Regenerating a general SDK from the route table would be a third thing to
  keep honest; the OpenAPI document is the general description.
- **`/docs/openapi.json` and `.yaml` stay, and are the live route table**: FastAPI's own
  `app.openapi()`, plus a description, a contact, the licence and the server. What was
  layered on top is removed because it was false: a blanket "every endpoint takes a
  bearer token or an API key" (the native document already states each route's own
  requirement), tags for groups that do not exist, examples for schemas that do not
  exist, an MIT licence (the project is AGPL), and a production server on a domain the
  product does not own. No server is named at all: a document without one describes the
  host it was fetched from, which stays true behind the TLS proxy, where
  `request.base_url` reports `http`.
- **Rate limits in the description are read from the running settings and the plan
  table**, not typed: the per-caller limit on `/api/v1`, and each plan's ceiling for an
  API key on the serving routes. A test changes a setting and expects the text to follow.
- **The SDK smoke test runs the real server as a subprocess** (integration-marked: it
  needs MongoDB and LocalStack): upload, train, fetch the model's generated Python SDK,
  mint an API key through the API, execute the SDK source and call `predict`. Only a
  running instance can show that a generated client reaches a real endpoint.
- AC4 (re-check after the A/B decision) stays open on #502, which is gated on the owner.
  Because the document is now the route table, removing those routes removes them here
  with no further change.

## Steps
- [x] Tests: the document is the route table; the description names no path and no limit
      the app does not have; removed endpoints 404; the dead-domain guard loses its exception.
- [x] `api_documentation.py` reduced to the published document; routes in `main.py`.
- [x] SDK smoke test against a live server. It found that the generated sample record
      used engineered feature names; fixed in `_sdk_inputs`.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
