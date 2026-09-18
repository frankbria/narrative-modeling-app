// frontend/lib/invite-allowlist.ts
//
// Signup gate (issues #261, #768).
//
// `SIGNUP_MODE=invite|open` decides who may sign in; the FastAPI backend reads
// the same two variables and mirrors this check as defense-in-depth
// (app/config.py::resolve_signup_mode / signup_admits). Keep the two in step.
//
// Unset used to mean "open" whenever `INVITE_ALLOWLIST` was also empty, so
// opening signup was one deleted variable. Now unset in production is `invite`
// (fails closed, like the admin allowlist), and invite mode with an empty list
// admits nobody. Dev/test with nothing set stays open so local runs and e2e
// need no configuration.

export type SignupMode = 'invite' | 'open';

type SignupEnv = Record<string, string | undefined>;

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
 * Which signup model applies. An explicit `invite`/`open` wins; unset in
 * production is `invite`; unset in dev/test is `invite` only if an allowlist is
 * configured; any other value is a typo and fails closed to `invite`.
 */
export function resolveSignupMode(
  raw: string | undefined | null,
  allowlist: Set<string>,
  production: boolean,
): SignupMode {
  const value = (raw ?? '').trim().toLowerCase();
  if (value === 'invite' || value === 'open') return value;
  if (value || production) return 'invite';
  return allowlist.size > 0 ? 'invite' : 'open';
}

/** The signup mode for `env` (defaults to this process's environment). */
export function signupMode(env: SignupEnv = process.env): SignupMode {
  return resolveSignupMode(
    env.SIGNUP_MODE,
    parseAllowlist(env.INVITE_ALLOWLIST),
    env.NODE_ENV === 'production',
  );
}

/**
 * Decide whether a sign-in attempt passes the signup gate.
 *
 * Open mode admits everyone. Invite mode admits a federated OAuth sign-in whose
 * attested email is on the allowlist. The credentials provider (registered only
 * in dev/test) self-attests its email, so it must never satisfy the email gate —
 * it passes only in open mode.
 *
 * @param env defaults to `process.env` (injectable for tests).
 */
export function isSignInAllowed(
  provider: string | null | undefined,
  email: string | null | undefined,
  env: SignupEnv = process.env,
): boolean {
  if (signupMode(env) === 'open') return true;
  if (provider === 'credentials' || !email) return false;
  return parseAllowlist(env.INVITE_ALLOWLIST).has(email.trim().toLowerCase());
}
