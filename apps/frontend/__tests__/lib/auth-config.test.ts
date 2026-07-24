import { missingAuthEnv, assertAuthConfig } from '@/lib/auth-config';

const FULL = {
  NEXTAUTH_SECRET: 's',
  NEXTAUTH_URL: 'https://app.example.com',
  GOOGLE_CLIENT_ID: 'gid',
  GOOGLE_CLIENT_SECRET: 'gsec',
  GITHUB_ID: 'hid',
  GITHUB_SECRET: 'hsec',
};

describe('missingAuthEnv', () => {
  it('is disabled (returns []) outside production', () => {
    expect(missingAuthEnv({}, 'development')).toEqual([]);
    expect(missingAuthEnv({}, 'test')).toEqual([]);
    expect(missingAuthEnv({}, undefined)).toEqual([]);
  });

  it('returns [] in production when all vars are present (even dummy values)', () => {
    expect(missingAuthEnv(FULL, 'production')).toEqual([]);
    // CI builds with dummy but non-empty values — must not trip the guard.
    const dummy = {
      NEXTAUTH_SECRET: 'test-secret-for-ci-only',
      NEXTAUTH_URL: 'http://localhost:3000',
      GOOGLE_CLIENT_ID: 'dummy-client-id',
      GOOGLE_CLIENT_SECRET: 'dummy-client-secret',
      GITHUB_ID: 'dummy-client-id',
      GITHUB_SECRET: 'dummy-client-secret',
    };
    expect(missingAuthEnv(dummy, 'production')).toEqual([]);
  });

  it('lists every missing or blank var in production', () => {
    expect(missingAuthEnv({}, 'production')).toEqual([
      'NEXTAUTH_SECRET',
      'NEXTAUTH_URL',
      'GOOGLE_CLIENT_ID',
      'GOOGLE_CLIENT_SECRET',
      'GITHUB_ID',
      'GITHUB_SECRET',
    ]);
    expect(missingAuthEnv({ ...FULL, GITHUB_SECRET: '   ' }, 'production')).toEqual([
      'GITHUB_SECRET',
    ]);
  });
});

describe('assertAuthConfig', () => {
  it('does not throw when nothing is missing', () => {
    expect(() => assertAuthConfig(FULL, 'production')).not.toThrow();
    expect(() => assertAuthConfig({}, 'development')).not.toThrow();
  });

  it('throws a clear error naming the missing vars in production', () => {
    expect(() => assertAuthConfig({ ...FULL, NEXTAUTH_SECRET: '' }, 'production')).toThrow(
      /NEXTAUTH_SECRET/,
    );
    // #317: blank NEXTAUTH_URL would let NextAuth infer a wrong redirect URI behind nginx.
    expect(() => assertAuthConfig({ ...FULL, NEXTAUTH_URL: '' }, 'production')).toThrow(
      /NEXTAUTH_URL/,
    );
  });
});
