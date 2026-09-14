import {
  missingAuthEnv,
  assertAuthConfig,
  assertDatabaseConfig,
  databaseNameFromUri,
} from '@/lib/auth-config';

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


describe('databaseNameFromUri', () => {
  it('returns the path database for bare and srv URIs, with or without options', () => {
    expect(databaseNameFromUri('mongodb://localhost:27017/mydb')).toBe('mydb');
    expect(
      databaseNameFromUri('mongodb+srv://u:p@cluster.mongodb.net/narrative_staging?retryWrites=true')
    ).toBe('narrative_staging');
    expect(databaseNameFromUri('mongodb://h1,h2,h3/mydb?replicaSet=rs0')).toBe('mydb');
  });

  it('returns null when the URI carries no database', () => {
    expect(databaseNameFromUri('mongodb://localhost:27017')).toBeNull();
    expect(databaseNameFromUri('mongodb://localhost:27017/')).toBeNull();
    expect(databaseNameFromUri('mongodb+srv://u:p@cluster.mongodb.net/?w=majority')).toBeNull();
    expect(databaseNameFromUri(undefined)).toBeNull();
  });
});

describe('assertDatabaseConfig', () => {
  const bare = 'mongodb://localhost:27017';
  const withPath = 'mongodb+srv://u:p@c.mongodb.net/narrative_staging?w=majority';

  it('throws in production when the URI is bare and MONGODB_DB is unset (AC1)', () => {
    expect(() => assertDatabaseConfig({ MONGODB_URI: bare }, 'production')).toThrow(
      /MONGODB_DB/
    );
  });

  it('throws in production when the URI path and MONGODB_DB disagree (AC2)', () => {
    expect(() =>
      assertDatabaseConfig(
        { MONGODB_URI: withPath, MONGODB_DB: 'narrative_modeling-staging' },
        'production'
      )
    ).toThrow(/different databases/);
  });

  it('starts in production when the URI carries the db and MONGODB_DB is unset (AC3)', () => {
    expect(() =>
      assertDatabaseConfig({ MONGODB_URI: withPath }, 'production')
    ).not.toThrow();
  });

  it('starts when MONGODB_DB is set (bare URI) or agrees with the URI path', () => {
    expect(() =>
      assertDatabaseConfig({ MONGODB_URI: bare, MONGODB_DB: 'narrative_staging' }, 'production')
    ).not.toThrow();
    expect(() =>
      assertDatabaseConfig(
        { MONGODB_URI: withPath, MONGODB_DB: 'narrative_staging' },
        'production'
      )
    ).not.toThrow();
  });

  it('is a no-op outside production (AC4)', () => {
    // The worst case (bare URI, no db) must NOT throw in dev/test/next build.
    for (const env of ['development', 'test', undefined]) {
      expect(() => assertDatabaseConfig({ MONGODB_URI: bare }, env)).not.toThrow();
    }
  });
});
