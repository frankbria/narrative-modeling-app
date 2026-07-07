// frontend/lib/invite-allowlist.ts
//
// Invite-only beta gate (issue #261).
//
// The launch is a free, invite-only beta, but OAuth signup is open by default —
// anyone with a Google/GitHub account could sign in and consume unbounded
// compute (AutoML, SHAP, batch prediction). This restricts sign-in to an
// env-configured email allowlist (`INVITE_ALLOWLIST`, comma-separated). The
// FastAPI backend reads the same var and mirrors this check as defense-in-depth
// (app/config.py / app/auth/nextauth_auth.py).
//
// An EMPTY / unset list DISABLES the gate (allow all) so local dev, tests, and
// any not-yet-configured deploy keep working. Production fail-closed is enforced
// at the deploy layer: staging compose requires INVITE_ALLOWLIST via `${VAR:?}`
// (same pattern as the CORS/S3 deploy guards, issues #256/#257).

/** Parse a comma-separated allowlist into a lowercased, trimmed set of emails. */
export function parseAllowlist(raw: string | undefined | null): Set<string> {
  if (!raw) return new Set();
  return new Set(
    raw
      .split(',')
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),
  );
}

/**
 * True if `email` may sign in.
 *
 * An empty allowlist means the gate is disabled — everyone is allowed. When the
 * gate is active, the email must be present on the list (case-insensitive); a
 * missing email is rejected.
 *
 * @param raw defaults to `process.env.INVITE_ALLOWLIST` (injectable for tests).
 */
export function isEmailAllowed(
  email: string | null | undefined,
  raw: string | undefined | null = process.env.INVITE_ALLOWLIST,
): boolean {
  const allowlist = parseAllowlist(raw);
  if (allowlist.size === 0) return true; // gate disabled
  if (!email) return false;
  return allowlist.has(email.trim().toLowerCase());
}

/**
 * Decide whether a sign-in attempt passes the invite gate.
 *
 * The credentials provider (registered only in dev/test) self-attests its
 * email, so it must never satisfy the email gate — it may pass only when the
 * gate is disabled (empty allowlist). Federated OAuth providers are checked
 * against the allowlist by their attested email.
 *
 * @param raw defaults to `process.env.INVITE_ALLOWLIST` (injectable for tests).
 */
export function isSignInAllowed(
  provider: string | null | undefined,
  email: string | null | undefined,
  raw: string | undefined | null = process.env.INVITE_ALLOWLIST,
): boolean {
  if (provider === 'credentials') return isEmailAllowed(null, raw);
  return isEmailAllowed(email, raw);
}
