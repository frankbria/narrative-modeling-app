# Issue #483 — [P1.8] [security] X-Forwarded-For handling lets a client choose its own rate-limit identity

Plan source: self-authored (issue had no plan comment). No architectural fork; approved autonomously.

## Design

- nginx sets `X-Real-IP $remote_addr` in every proxied location and **overwrites** it, so behind nginx it is authoritative. `X-Forwarded-For` is **appended** (`$proxy_add_x_forwarded_for`), so element `[0]` is client-controlled — the middleware stops reading XFF entirely.
- The trust flag still expresses a real choice ("is a trusted proxy in front of me that sets X-Real-IP?"), so it stays, renamed `RATE_LIMIT_TRUST_PROXY` (kwarg `trust_proxy`) so the name matches what it reads. No deployed environment sets the old name (staging compose never passed it).
- Staging compose passes `RATE_LIMIT_TRUST_PROXY: "true"` as a literal — compose is the contract (#457); without it staging buckets every anonymous request under nginx's container IP.
- Under **both** flag settings a spoofed `X-Forwarded-For` (and, when untrusted, a spoofed `X-Real-IP`) resolves to the socket peer.

## Steps

1. [ ] Middleware: replace `_client_ip` with module-level `client_ip(request, trust_proxy)` reading `x-real-ip` only when trusted; rename kwarg/setting; update module docstring. Files: `apps/backend/app/middleware/rate_limit.py`, `apps/backend/app/config.py`, `apps/backend/.env.example`.
2. [ ] Tests (AC4, AC5): direct key-derivation tests on `client_ip` — spoofed XFF under both settings → peer; X-Real-IP honoured only when trusted; middleware-level test that a varying XFF does not mint buckets when trusted. File: `apps/backend/tests/test_middleware/test_rate_limit.py`.
3. [ ] Agreement guard (AC2): new `apps/backend/tests/test_security/test_nginx_real_ip.py` — every `location` proxying to the backend upstream sets `proxy_set_header X-Real-IP $remote_addr;` and staging compose passes `RATE_LIMIT_TRUST_PROXY: "true"` to the backend. Reuses the parser helpers from `test_nginx_webhook_route.py`.
4. [ ] Compose: add `RATE_LIMIT_TRUST_PROXY: "true"` to the backend service in `docker-compose.staging.yml`.
5. [ ] Docs: CLAUDE.md rate-limiting bullet + `tasks/lessons.md` line about the flag.

## Acceptance criteria

- [ ] AC1 client IP from `X-Real-IP` (nginx-authoritative), never XFF[0]
- [ ] AC2 nginx and middleware agree — test parses the real config against the real header
- [ ] AC3 correct under both flag settings; flag renamed to express the real choice
- [ ] AC4 test: spoofed XFF does not create a new bucket
- [ ] AC5 tests exercise the key-derivation function directly (limiter disabled in test env otherwise)

## Known limitation

The live nginx on staging is hand-maintained and has diverged from the repo (#594). The repo config sets X-Real-IP; the operator must confirm the live file does too before trusting the flag there. Follow-up comment on #594.
