# Issue #915: generated SDKs and stored deployment endpoints use http:// behind the TLS proxy

## Problem
`deploy_model` and `_serving_endpoint_for` build the customer-facing serving URL from
`request.base_url`. gunicorn trusts `X-Forwarded-Proto` from loopback only and nginx
connects from the Docker bridge, so on a deployed instance the URL is `http://…`.

Confirmed on staging (AC1): a request to the backend's own port carrying
`X-Forwarded-Proto: https` gets a slash redirect to `http://…`. Stored endpoints there
(AC4): 0 models, 0 endpoints, 0 starting `http://`.

## Decision
The public base URL comes from configuration, not from forwarded headers. Trusting the
headers means uvicorn also rewrites `request.client` from `X-Forwarded-For`, which the
rate limiter deliberately never reads (#455). A configured URL trusts nothing a client sends.

## Plan
- [ ] RED: `tests/test_api/test_public_serving_url.py`: with `PUBLIC_API_URL` set, deploy
      stores and the SDK compiles in `https://…`, whatever Host or forwarded headers the
      request carries; unset, the request's own base is used (local development).
- [ ] `app/config.py::public_api_url()`; `model_training._public_api_base(request)` used by
      both builders.
- [ ] `docker-compose.staging.yml`: backend gets `PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-}`,
      the value the frontend is already built with, so no new variable to provision. A test
      pins the wiring.
- [ ] `.env.example` note, CLAUDE.md, gate, review, demo, PR.

## Out of scope
- `--forwarded-allow-ips` (see Decision).
- A script to rewrite stored `http://` endpoints: none exist on staging.
