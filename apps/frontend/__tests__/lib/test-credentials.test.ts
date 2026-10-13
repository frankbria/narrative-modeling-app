/**
 * Dev/test admin identity (#613).
 *
 * The credentials provider is registered only in development/test. It used to
 * accept exactly one identity, so an e2e run could not be both a non-admin and
 * an admin; this second identity exists so the /admin smoke spec can sign in as
 * someone on ADMIN_EMAILS while the ordinary test user stays off it.
 */
import {
  resolveExtraTestIdentity,
  resolveIsolatedTestUser,
  resolveTestAdmin,
} from '@/lib/test-credentials';

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

/**
 * Isolated e2e users (#743). Every spec shared one account, so a spec that reset
 * its onboarding or erased its data changed what every other spec started from.
 */
describe('resolveIsolatedTestUser', () => {
  const BASE = 'e2e@fixture.test';
  const SECRET = 'e2e-user-secret-1';
  const on = { TEST_ISOLATED_USERS: '1', TEST_USER_EMAIL: BASE, TEST_USER_PASSWORD: SECRET };

  it('accepts a plus-addressed form of the test user, as its own account', () => {
    const user = resolveIsolatedTestUser('e2e+onboarding@fixture.test', SECRET, on);
    expect(user).toEqual({
      id: 'test-isolated-onboarding',
      email: 'e2e+onboarding@fixture.test',
      name: 'Test User (onboarding)',
      image: null,
    });
  });

  it('gives two slugs two accounts, neither the shared user nor the admin', () => {
    const a = resolveIsolatedTestUser('e2e+erasure@fixture.test', SECRET, on);
    const b = resolveIsolatedTestUser('e2e+12345@fixture.test', SECRET, on);
    expect(a?.id).not.toBe(b?.id);
    for (const id of [a?.id, b?.id]) {
      expect(id).not.toBe('test-user-12345');
      expect(id).not.toBe('test-admin-12345');
    }
  });

  it('does not exist unless the run asked for it', () => {
    const email = 'e2e+onboarding@fixture.test';
    expect(resolveIsolatedTestUser(email, SECRET, { ...on, TEST_ISOLATED_USERS: undefined })).toBeNull();
    expect(resolveIsolatedTestUser(email, SECRET, { ...on, TEST_ISOLATED_USERS: 'true' })).toBeNull();
    expect(resolveIsolatedTestUser(email, SECRET, { ...on, TEST_USER_EMAIL: undefined })).toBeNull();
    expect(resolveIsolatedTestUser(email, SECRET, { ...on, TEST_USER_PASSWORD: undefined })).toBeNull();
    // an address with no @ has no mailbox to plus-address
    expect(resolveIsolatedTestUser('e2+x', SECRET, { ...on, TEST_USER_EMAIL: 'e2e' })).toBeNull();
  });

  it('refuses a wrong secret, another mailbox or domain, and a slug that is not a plain word', () => {
    expect(resolveIsolatedTestUser('e2e+onboarding@fixture.test', 'wrong', on)).toBeNull();
    expect(resolveIsolatedTestUser('other+onboarding@fixture.test', SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser('e2e+onboarding@elsewhere.test', SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser('e2e+@fixture.test', SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser('e2e+a/../b@fixture.test', SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser('e2e+UPPER@fixture.test', SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser(`e2e+${'a'.repeat(33)}@fixture.test`, SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser(BASE, SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser(undefined, SECRET, on)).toBeNull();
    expect(resolveIsolatedTestUser('e2e+onboarding@fixture.test', undefined, on)).toBeNull();
  });
});

describe('resolveExtraTestIdentity', () => {
  const USER_SECRET = 'e2e-user-secret-1';
  const env = {
    TEST_ADMIN_EMAIL: ADMIN_EMAIL,
    TEST_ADMIN_PASSWORD: ADMIN_SECRET,
    TEST_ISOLATED_USERS: '1',
    TEST_USER_EMAIL: 'e2e@fixture.test',
    TEST_USER_PASSWORD: USER_SECRET,
  };

  it('is the admin, an isolated user, or nobody', () => {
    expect(resolveExtraTestIdentity(ADMIN_EMAIL, ADMIN_SECRET, env)?.id).toBe('test-admin-12345');
    expect(resolveExtraTestIdentity('e2e+erasure@fixture.test', USER_SECRET, env)?.id).toBe(
      'test-isolated-erasure',
    );
    expect(resolveExtraTestIdentity('nobody@fixture.test', USER_SECRET, env)).toBeNull();
  });
});
