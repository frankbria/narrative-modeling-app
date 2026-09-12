# Issue #550 — [P2.33] [security] Security Audit went red — npm advisories against existing frontend deps

Plan source: self-authored (issue has ACs, no plan). Approved autonomously — lockfile + one pinned patch bump, no fork.

## Findings (2026-09-12, live advisory DB)
- The audit has grown from the issue's 6 to 9: the original browserslist ×2 / js-yaml / nanoid / dompurify, plus brace-expansion (high), @humanfs/node, baseline-browser-mapping (moderate), and — new and real — **next 16.2.12: critical** (GHSA-p293-qw3h-jr36 Windows RCE; GHSA-2xp9-vwfh-vxw4 unauthenticated RCE in the Image Optimization API with AVIF) with sharp (high) riding along. Fix: next 16.3.5, same major.
- CI's job runs `npm audit --audit-level=high`; the issue's AC1 asks for clean at `moderate`.
- `next` and `eslint-config-next` are pinned exactly (16.2.12); `npm audit fix` cannot cross a pin, so the bump is explicit and both move together.
- Dependabot #600 bumps next to 16.3.4 (still vulnerable) and is red; superseded once this merges.

## Steps
- [x] `npm audit fix` (non-breaking): 8 of 9 gone, lockfile only
- [x] `npm i --save-exact next@16.3.5 eslint-config-next@16.3.5`
- [ ] audit = 0 at moderate; jest, tsc, lint cap 230, next build
- [ ] PR → CI (Security Audit must be green this time) → merge; comment/close #600
