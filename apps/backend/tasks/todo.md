# Issue #569 — [P2.36] [security] pip-audit flags cryptography 49.0.0 (PYSEC-2026-3552) — fix available in 50.0.0

Plan source: self-authored. No architectural fork; approved autonomously.

## Design
- `cryptography` is transitive (`python-jose[cryptography]>=3.5.0`); bump it in `uv.lock` only via `uv lock --upgrade-package cryptography` — no new direct dependency (AC1). python-jose 3.5.0 accepts 50.x.
- Advisory verified against OSV: PYSEC-2026-3552 = CVE-2026-69247 / GHSA-g6cj-pr64-35w5, PKCS#7 EnvelopedData Bleichenbacher oracle, affected [44.0.0, 50.0.0). The backend never touches PKCS#7 (jose uses cryptography for JWT signature primitives), so exploitability here is nil — the point is the smoke detector (AC2).
- AC4: the `ignored 1` is `PYSEC-2026-1325`, already justified in ci.yml's `--ignore-vuln` comment; quote it in the PR rather than re-litigate.
- Dependabot: pip ecosystem is configured weekly with a 14-day cooldown; a transitive-only package gets no version-update PR, and a security PR needs a Dependabot alert — check whether alerts are enabled and record the finding.

## Steps
1. [ ] `uv lock --upgrade-package cryptography` (49.0.0 → 50.0.1)
2. [ ] pip-audit exactly as CI does → 0 known vulnerabilities (1 ignored)
3. [ ] `uv sync --frozen`; auth + API-key suites green (the jose/cryptography path)
4. [ ] Demo: audit before/after
5. [ ] Record the Dependabot observation on the issue

## Acceptance criteria
- [ ] AC1 cryptography ≥ 50.0.0 via the lock, no new direct dep
- [ ] AC2 backend half of Security Audit green on main (verified after merge)
- [ ] AC3 n/a — the bump was not blocked
- [ ] AC4 ignored advisory identified + justified (PYSEC-2026-1325, ci.yml)
