# #830 — Move staging to dev.sheetpredict.app (P1.59)

Self-authored plan (the issue carries acceptance criteria, no plan). Read-only probe of
the box on 2026-10-10: the edge is in sync with the repo, `NGINX_SERVER_NAME` is still the
old name, six `.env.staging` lines carry it, `/var/www/letsencrypt` does not exist, port 80
does not answer the new name, and static assets are served without HSTS.

## Decisions made here
- **AC4 guard lives in the template, keyed on the hostname.** #832 AC4 renders production
  from this same template with only the placeholders differing, so a hard-coded header
  would ship `noindex` to production. A `map $host` defaults to `noindex, nofollow` and
  maps only `www.sheetpredict.app` to empty (nginx omits an empty header). It fails
  closed and needs no new env variable or script change.
- **Every response means every location.** nginx drops all inherited `add_header` lines in
  a location that declares its own. The static-asset location does, which is why those
  responses carry no HSTS today. It switches to `expires 1d` (same one-day intent) and a
  test bans location-level `add_header`.
- **AC5: the old name is removed, not redirected.** Staging has no users or search
  presence to carry over, and a 301 needs conditional rendering in a `sed` template.
  The old certificate is deleted at the cutover so its renewal stops.
- **First certificate uses certbot's nginx authenticator**, as the box's other
  certificates do, because port 80 cannot serve the webroot for the new name until the
  cutover renders it. It moves to the webroot after the cutover (AC1's renewal check).

## Steps
1. RED: `tests/test_security/test_nginx_noindex.py`.
2. GREEN: `nginx-staging.conf` (map, header in both server blocks, `expires 1d`).
3. Docs: `.env.staging.example` (`NGINX_SERVER_NAME`), compose comment, STAGING.md,
   CLAUDE.md edge bullet.
4. Demo: render the template into a real nginx container and curl both hostnames.
5. After merge: deploy applies the edge; verify the header live. Box: create the
   webroot, issue the certificate.
6. Cutover runbook on #830 for the steps that need the owner's OAuth and Stripe consoles.

## Acceptance criteria
- [ ] AC1 certificate for dev.sheetpredict.app, renewal dry run (box)
- [ ] AC2 `.env.staging` carries the new host; edge shipped by a deploy, no drift (cutover)
- [ ] AC3 OAuth callbacks and Stripe webhook point at the new host (owner consoles)
- [ ] AC4 `X-Robots-Tag: noindex, nofollow` on every staging response, pinned by a test
- [ ] AC5 old name retired, decision recorded (cutover)
- [ ] AC6 health gates and hand smoke checks against the new host (cutover)
