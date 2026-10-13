// frontend/lib/test-credentials.ts
//
// The identities the development/test-only credentials provider accepts beyond
// the ordinary test user: an admin (#613) and isolated e2e users (#743, below).
//
// The admin: the e2e run needs an ordinary tenant (off ADMIN_EMAILS) and an admin
// (on it) in the same server process, because the /admin guard's final HTTP
// status can only be observed end to end. The admin identity exists only when
// BOTH TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD are set — there is no default,
// so a server that was not told about it has no second identity at all.
// auth.ts registers the credentials provider only in development or test.

export interface TestIdentity {
  id: string;
  email: string;
  name: string;
  image: null;
}

type Env = Record<string, string | undefined>;

export function resolveTestAdmin(
  email: string | undefined,
  secret: string | undefined,
  env: Env = process.env,
): TestIdentity | null {
  const adminEmail = env.TEST_ADMIN_EMAIL;
  const adminSecret = env.TEST_ADMIN_PASSWORD;
  if (!adminEmail || !adminSecret || !email || !secret) return null;
  // Plain comparison, like the test-user check beside it: this provider exists
  // only in development/test builds, so timing safety buys nothing here.
  if (email !== adminEmail || secret !== adminSecret) return null;
  return { id: 'test-admin-12345', email: adminEmail, name: 'Test Admin', image: null };
}

const ISOLATED_SLUG = /^[a-z0-9-]{1,32}$/;

/**
 * An account of its own for a spec that changes account-scoped state (#743):
 * `local+slug@domain` of TEST_USER_EMAIL, with the test user's password. Every
 * spec used to share one account, so one that reset its onboarding or erased its
 * data changed what the others started from. Exists only when the run sets
 * TEST_ISOLATED_USERS=1 and both test-user variables: like the admin, no default.
 */
export function resolveIsolatedTestUser(
  email: string | undefined,
  secret: string | undefined,
  env: Env = process.env,
): TestIdentity | null {
  const run = isolatedRun(env);
  if (!run || !email || secret !== run.password) return null;
  const slug = isolatedSlug(email, run.base);
  if (!slug) return null;
  return { id: `test-isolated-${slug}`, email, name: `Test User (${slug})`, image: null };
}

/** The test user's address and password, when this run turned isolated users on. */
function isolatedRun(env: Env): { base: string; password: string } | null {
  const base = env.TEST_USER_EMAIL;
  const password = env.TEST_USER_PASSWORD;
  if (env.TEST_ISOLATED_USERS !== '1' || !base || !password) return null;
  return { base, password };
}

/** The slug in `local+slug@domain`, when `email` is that form of `base` and the slug is a plain word. */
function isolatedSlug(email: string, base: string): string | null {
  const at = base.lastIndexOf('@');
  const prefix = `${base.slice(0, at)}+`;
  const domain = base.slice(at);
  if (!email.startsWith(prefix) || !email.endsWith(domain)) return null;
  const slug = email.slice(prefix.length, email.length - domain.length);
  return ISOLATED_SLUG.test(slug) ? slug : null;
}

/** Every identity the provider accepts beyond the ordinary test user. */
export function resolveExtraTestIdentity(
  email: string | undefined,
  secret: string | undefined,
  env: Env = process.env,
): TestIdentity | null {
  return resolveTestAdmin(email, secret, env) ?? resolveIsolatedTestUser(email, secret, env);
}
