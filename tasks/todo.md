# Issue #456 — [P0.13] Stripe webhooks 404 at the nginx edge

Backend mounts `POST /webhooks/stripe/webhook` (`app/main.py:330`), deliberately
**outside** `/api/v1` so `RateLimitMiddleware` can't 429 Stripe's small IP pool (#367).
`nginx-staging.conf` only has `location /api/` and `location /`, so the webhook falls
through to Next.js and 404s. Every `checkout.session.completed` /
`customer.subscription.*` event is lost: payment succeeds, entitlement never follows.

## Findings from recon (drives the plan)

1. **The repo config is NOT the applied config.** `/etc/nginx/sites-available/narrative-staging.conf`
   on the VPS is a 53-line hand-written file (`server_name dev.briaanalytics.com`,
   certbot-managed TLS, `proxy_pass http://localhost:8010/api/;`), last modified
   **2026-07-01**. The repo file is 187 lines, still carries placeholder
   `narrative.yourdomain.com` server names and cert paths, and has never been applied —
   it *cannot* be applied verbatim. Fixing only the repo file changes nothing live.
   → AC5. Needs a follow-up issue for making the edge config managed.
2. **No `STRIPE_*` env reaches the staging backend container** (`printenv` shows
   `ENVIRONMENT` and nothing else from `STRIPE_*`/`PLAN_*`). That is #457 (P0.14).
   Consequence for AC4: on staging a signed event can only be proven to *reach the
   handler* (400 "signature verification failed" instead of 404). The
   "a `Subscription` document is actually written" half of AC4 is demonstrated
   **locally**, through a real nginx running the same location block.

## Plan

1. **(RED)** `apps/backend/tests/test_security/test_nginx_webhook_route.py` — parse the
   real `nginx-staging.conf` and assert:
   - a `location` block matching `/webhooks/stripe/` exists and `proxy_pass`es to the
     backend upstream (not the frontend);
   - it does not append a rewriting URI to `proxy_pass`;
   - `proxy_request_buffering off` (stream the raw bytes; no buffering that could
     re-frame the body);
   - no `sub_filter` / `charset` / body-altering directive inside it;
   - the webhook path in the config matches the path the backend actually mounts
     (`/webhooks/stripe` prefix, read from `app/main.py`) so the two can't drift.
2. **(GREEN)** Add the `location /webhooks/stripe/` block to `nginx-staging.conf`,
   placed before `location /`.
3. **Apply the same block to the live edge config** on the VPS, `nginx -t`, reload.
4. **Demo (AC4)**: local nginx in front of the local backend with a real
   `STRIPE_WEBHOOK_SECRET`; POST a genuinely-signed `checkout.session.completed`
   through the proxy; assert HTTP 200 **and** a `Subscription` document in Mongo.
   Then on staging: same signed request → assert it now reaches the handler
   (400 signature-verification, not 404 from Next.js).
5. **AC5**: comment the drift finding on #456 and open a prioritized follow-up issue
   for the unmanaged edge config.

## Autonomous decisions (no architectural fork)

- Prefix `location /webhooks/stripe/` rather than a regex/exact match — matches the
  file's existing style and the backend's mount prefix.
- Repo block uses the file's `narrative_backend` upstream; the live block uses the live
  file's `http://localhost:8010` style. Two files, two idioms, same routing.
- The Subscription-write assertion runs locally, not on staging, because staging is
  blocked on #457. Documented as a Known Limitation rather than silently skipped.

## Acceptance criteria

- [ ] AC1 `nginx-staging.conf` proxies the webhook path to the backend upstream
- [ ] AC2 raw request body passes through unmodified (signature still verifies)
- [ ] AC3 `Stripe-Signature` header is forwarded
- [ ] AC4 verified end-to-end with a real signed event, asserting a `Subscription` write
- [ ] AC5 confirmed whether the repo config is the applied one; follow-up filed if not
