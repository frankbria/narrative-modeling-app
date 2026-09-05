/**
 * Regression guard for the NextAuth adapter's database name.
 *
 * `MongoDBAdapter(client)` with no options runs `client.db(undefined)`, which
 * against this repo's bare `MONGODB_URI` resolves to the database literally
 * named `test` — silently sending users and accounts somewhere the backend
 * never looks. Nothing else in the suite imports `auth.ts`, so dropping the
 * `{ databaseName }` option would otherwise reintroduce that bug green.
 */

// `@auth/mongodb-adapter` is ESM-only (exports map has no `require`), so jest's
// CJS resolver cannot load the real module — hence the virtual mock, and hence
// no other suite importing auth.ts.
jest.mock(
  '@auth/mongodb-adapter',
  () => ({ MongoDBAdapter: jest.fn(() => ({})) }),
  { virtual: true }
)

jest.mock('next-auth', () => ({
  __esModule: true,
  default: jest.fn(() => ({
    handlers: {},
    signIn: jest.fn(),
    signOut: jest.fn(),
    auth: jest.fn(),
  })),
}))

// next-auth's provider entry points are ESM re-exports of @auth/core — same
// resolver problem, and irrelevant to what this test asserts.
// (inlined rather than shared: jest.mock is hoisted above any const)
const provider = { __esModule: true, default: jest.fn(() => ({ id: 'stub' })) }
jest.mock('next-auth/providers/google', () => provider, { virtual: true })
jest.mock('next-auth/providers/github', () => provider, { virtual: true })
jest.mock('next-auth/providers/credentials', () => provider, { virtual: true })

jest.mock('@/lib/db', () => ({ __esModule: true, default: { stubClient: true } }))

/** Load auth.ts fresh with MONGODB_DB set to `value` and return the adapter's options arg. */
function adapterOptionsWithDb(value: string | undefined) {
  const previous = process.env.MONGODB_DB
  if (value === undefined) {
    delete process.env.MONGODB_DB
  } else {
    process.env.MONGODB_DB = value
  }

  let options: unknown
  jest.isolateModules(() => {
    const { MongoDBAdapter } = require('@auth/mongodb-adapter')
    ;(MongoDBAdapter as jest.Mock).mockClear()
    require('@/auth')
    options = (MongoDBAdapter as jest.Mock).mock.calls[0][1]
  })

  if (previous === undefined) {
    delete process.env.MONGODB_DB
  } else {
    process.env.MONGODB_DB = previous
  }
  return options
}

describe('auth.ts MongoDB adapter wiring', () => {
  it('names the database from MONGODB_DB', () => {
    expect(adapterOptionsWithDb('narrative_modeling-staging')).toEqual({
      databaseName: 'narrative_modeling-staging',
    })
  })

  it('leaves the database undefined when MONGODB_DB is unset, preserving the old URI-default behaviour', () => {
    expect(adapterOptionsWithDb(undefined)).toEqual({ databaseName: undefined })
  })
})
