// frontend/lib/test-credentials.ts
//
// The second identity the development/test-only credentials provider accepts
// (#613). The e2e run needs an ordinary tenant (off ADMIN_EMAILS) and an admin
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
  if (email !== adminEmail || secret !== adminSecret) return null;
  return { id: 'test-admin-12345', email: adminEmail, name: 'Test Admin', image: null };
}
