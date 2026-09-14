// frontend/lib/auth-config.ts
//
// Fail-fast auth configuration guard (issue #271).
//
// `auth.ts` falls back to `dummy-client-id`/`dummy-client-secret` for OAuth
// creds and passes `NEXTAUTH_SECRET` through unchecked. A production deploy
// that forgets to set these would silently run with dummy OAuth + weak/absent
// JWT signing instead of failing. This asserts they are present at startup —
// but only in production: development/test legitimately run without real OAuth
// creds (the credentials provider + dummy fallbacks), so the guard is disabled
// there. Trigger is *missing/blank*, not "equals dummy", so CI's `next build`
// (which sets non-empty dummy values) is unaffected.
//
// NEXTAUTH_URL is also required (#317): a blank value makes NextAuth infer the
// base URL from request headers, producing wrong OAuth redirect URIs behind the
// nginx reverse proxy the app deploys under.

/** Env vars required for OAuth sign-in + JWT signing to work in production. */
export const REQUIRED_PROD_AUTH_ENV = [
  'NEXTAUTH_SECRET',
  'NEXTAUTH_URL',
  'GOOGLE_CLIENT_ID',
  'GOOGLE_CLIENT_SECRET',
  'GITHUB_ID',
  'GITHUB_SECRET',
] as const;

/**
 * Names of required auth env vars that are missing or blank.
 *
 * Returns `[]` outside production (guard disabled for dev/test). In production,
 * a var counts as present when it is a non-empty, non-whitespace string.
 */
export function missingAuthEnv(
  env: Record<string, string | undefined>,
  nodeEnv: string | undefined,
): string[] {
  if (nodeEnv !== 'production') return [];
  return REQUIRED_PROD_AUTH_ENV.filter((k) => !env[k]?.trim());
}

/**
 * Throw if any required auth env var is missing in production. No-op in dev/test.
 *
 * Called at `auth.ts` module load so a misconfigured production server fails to
 * start rather than running with dummy/weak auth.
 */
export function assertAuthConfig(
  env: Record<string, string | undefined> = process.env,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): void {
  const missing = missingAuthEnv(env, nodeEnv);
  if (missing.length > 0) {
    throw new Error(
      `[auth] Refusing to start: required auth environment variable(s) missing in production: ` +
        `${missing.join(', ')}. Set them, or run with NODE_ENV=development for local use.`,
    );
  }
}

/**
 * The database named in a MongoDB connection string's path, or null when it
 * carries none. Handles `mongodb://` and `mongodb+srv://`, credentials in the
 * authority, multiple comma-separated hosts, and a trailing `?options` string.
 * The path is the segment after the first `/` following the host list.
 */
export function databaseNameFromUri(uri: string | undefined): string | null {
  if (!uri) return null;
  const afterScheme = uri.replace(/^mongodb(\+srv)?:\/\//i, '');
  const noQuery = afterScheme.split('?')[0];
  const slash = noQuery.indexOf('/');
  if (slash === -1) return null;
  const db = noQuery.slice(slash + 1).trim();
  return db || null;
}

/**
 * Fail fast (production only) when the database is not named exactly once (#551).
 *
 * The real invariant is "the database is named exactly once and both halves
 * agree", NOT "MONGODB_DB is set": a deploy may carry the database in the
 * MONGODB_URI path instead (see `.env.staging.example`). So:
 *   - bare URI (no path) AND no MONGODB_DB → error, because the adapter would
 *     silently fall back to `client.db(undefined)` → the `test` database (#545);
 *   - URI path AND MONGODB_DB set to a DIFFERENT name → error (the exact split
 *     #545 found: URI `narrative_staging` vs MONGODB_DB `narrative_modeling-staging`);
 *   - URI path with no MONGODB_DB, or the two agreeing → fine.
 * No-op outside production, matching `missingAuthEnv`.
 */
export function assertDatabaseConfig(
  env: Record<string, string | undefined> = process.env,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): void {
  if (nodeEnv !== 'production') return;
  const fromDb = env.MONGODB_DB?.trim() || null;
  const fromUri = databaseNameFromUri(env.MONGODB_URI);
  if (!fromDb && !fromUri) {
    throw new Error(
      '[auth] Refusing to start: no database name is configured. Set MONGODB_DB ' +
        '(the MONGODB_URI has no path), or the adapter falls back to the "test" ' +
        'database while the backend reads another (#545/#551).',
    );
  }
  if (fromDb && fromUri && fromDb !== fromUri) {
    throw new Error(
      `[auth] Refusing to start: MONGODB_DB (${fromDb}) and the MONGODB_URI path ` +
        `database (${fromUri}) name different databases; they must agree (#551).`,
    );
  }
}
