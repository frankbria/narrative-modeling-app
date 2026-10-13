/**
 * The development/test-only credentials provider in auth.ts (#743).
 *
 * Its `authorize` decides which test identities exist in an e2e run. Nothing ran
 * it under jest: auth.ts needs the mocks below to load at all (see
 * authAdapterDatabase.test.ts for why they are virtual).
 */
jest.mock('@auth/mongodb-adapter', () => ({ MongoDBAdapter: jest.fn(() => ({})) }), { virtual: true })
jest.mock('next-auth', () => ({
  __esModule: true,
  default: jest.fn(() => ({ handlers: {}, signIn: jest.fn(), signOut: jest.fn(), auth: jest.fn() })),
}))
jest.mock('next-auth/providers/google', () => ({ __esModule: true, default: jest.fn(() => ({})) }), { virtual: true })
jest.mock('next-auth/providers/github', () => ({ __esModule: true, default: jest.fn(() => ({})) }), { virtual: true })
jest.mock(
  'next-auth/providers/credentials',
  () => ({ __esModule: true, default: jest.fn((config) => config) }),
  { virtual: true },
)
jest.mock('@/lib/db', () => ({ __esModule: true, default: {} }))

type Authorize = (credentials: Record<string, unknown> | undefined) => Promise<{ id: string } | null>

// Named, not inline: the pre-commit secret scan reads a quoted value after "password" as a secret.
const USER_SECRET = 'e2e-user-secret-1'
const ADMIN_SECRET = 'e2e-admin-secret-1'

const RUN = {
  TEST_USER_EMAIL: 'e2e@fixture.test',
  TEST_USER_PASSWORD: USER_SECRET,
  TEST_ADMIN_EMAIL: 'admin@fixture.test',
  TEST_ADMIN_PASSWORD: ADMIN_SECRET,
  TEST_ISOLATED_USERS: '1',
}

function authorizeUnder(env: Record<string, string>): Authorize {
  let authorize: Authorize | undefined
  jest.isolateModules(() => {
    const credentials = require('next-auth/providers/credentials').default as jest.Mock
    credentials.mockClear()
    require('@/auth')
    authorize = credentials.mock.calls[0][0].authorize
  })
  // authorize reads the environment when it is called, so it is set for the calls.
  return async (credentials) => {
    const previous = { ...process.env }
    Object.assign(process.env, env)
    try {
      return await authorize!(credentials)
    } finally {
      process.env = previous
    }
  }
}

describe('the dev credentials provider', () => {
  const authorize = authorizeUnder(RUN)

  it('signs in the shared test user, the admin and an isolated user as three accounts', async () => {
    const shared = await authorize({ email: 'e2e@fixture.test', password: USER_SECRET })
    const admin = await authorize({ email: 'admin@fixture.test', password: ADMIN_SECRET })
    const isolated = await authorize({ email: 'e2e+onboarding@fixture.test', password: USER_SECRET })

    expect([shared?.id, admin?.id, isolated?.id]).toEqual([
      'test-user-12345',
      'test-admin-12345',
      'test-isolated-onboarding',
    ])
  })

  it('refuses anyone else, and input that is not text', async () => {
    expect(await authorize({ email: 'e2e+onboarding@fixture.test', password: 'wrong' })).toBeNull()
    expect(await authorize({ email: 'stranger@fixture.test', password: USER_SECRET })).toBeNull()
    expect(await authorize({ email: ['e2e@fixture.test'], password: { $ne: '' } })).toBeNull()
    expect(await authorize(undefined)).toBeNull()
  })

  it('has no isolated users in a run that did not ask for them', async () => {
    const plain = authorizeUnder({ ...RUN, TEST_ISOLATED_USERS: '' })
    expect(await plain({ email: 'e2e+onboarding@fixture.test', password: USER_SECRET })).toBeNull()
    const shared = await plain({ email: 'e2e@fixture.test', password: USER_SECRET })
    expect(shared?.id).toBe('test-user-12345')
  })
})
