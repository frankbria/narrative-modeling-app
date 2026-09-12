/**
 * Dev/test admin identity (#613).
 *
 * The credentials provider is registered only in development/test. It used to
 * accept exactly one identity, so an e2e run could not be both a non-admin and
 * an admin; this second identity exists so the /admin smoke spec can sign in as
 * someone on ADMIN_EMAILS while the ordinary test user stays off it.
 */
import { resolveTestAdmin } from '@/lib/test-credentials';

const ADMIN_EMAIL = 'admin-e2e@narrativeml.com';
const ADMIN_SECRET = 'e2e-admin-secret-1';
const env = { TEST_ADMIN_EMAIL: ADMIN_EMAIL, TEST_ADMIN_PASSWORD: ADMIN_SECRET };

describe('resolveTestAdmin', () => {
  it('accepts the admin identity with an id distinct from the test user', () => {
    const admin = resolveTestAdmin(ADMIN_EMAIL, ADMIN_SECRET, env);
    expect(admin).toEqual(expect.objectContaining({ email: ADMIN_EMAIL }));
    expect(admin?.id).not.toBe('test-user-12345');
  });

  it('refuses a wrong secret, another email, and missing input', () => {
    expect(resolveTestAdmin(ADMIN_EMAIL, 'wrong', env)).toBeNull();
    expect(resolveTestAdmin('someone@else.test', ADMIN_SECRET, env)).toBeNull();
    expect(resolveTestAdmin(undefined, ADMIN_SECRET, env)).toBeNull();
    expect(resolveTestAdmin(ADMIN_EMAIL, undefined, env)).toBeNull();
  });

  it('does not exist unless BOTH variables are set — and has no default', () => {
    expect(resolveTestAdmin(ADMIN_EMAIL, ADMIN_SECRET, { TEST_ADMIN_EMAIL: ADMIN_EMAIL })).toBeNull();
    expect(resolveTestAdmin(ADMIN_EMAIL, ADMIN_SECRET, { TEST_ADMIN_PASSWORD: ADMIN_SECRET })).toBeNull();
    expect(resolveTestAdmin(ADMIN_EMAIL, ADMIN_SECRET, {})).toBeNull();
  });
});
