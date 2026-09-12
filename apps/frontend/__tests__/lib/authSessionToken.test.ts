/**
 * The session exposes the minted API token and nothing from the OAuth provider (#527).
 *
 * `session.accessToken` used to carry the Google/GitHub access token to the
 * browser, and three call sites forwarded it to our own backend as the bearer.
 * Nothing legitimately needs a provider credential client-side, so the callbacks
 * must not persist it in the JWT or copy it onto the session.
 *
 * Same virtual-mock arrangement as authAdapterDatabase.test.ts: `@auth/mongodb-adapter`
 * and the provider entry points are ESM-only, so the real modules cannot load
 * under jest's CJS resolver.
 */

// Make this file a module: without an import/export, tsc treats it as a script
// whose top-level `const`s share one global scope with the sibling test's.
export {}

jest.mock(
  '@auth/mongodb-adapter',
  () => ({ MongoDBAdapter: jest.fn(() => ({})) }),
  { virtual: true }
)

// Capture the NextAuth config so the callbacks can be exercised directly.
const captured: { config?: Record<string, unknown> } = {}
jest.mock('next-auth', () => ({
  __esModule: true,
  default: jest.fn((config: Record<string, unknown>) => {
    captured.config = config
    return { handlers: {}, signIn: jest.fn(), signOut: jest.fn(), auth: jest.fn() }
  }),
}))

const provider = { __esModule: true, default: jest.fn(() => ({ id: 'stub' })) }
jest.mock('next-auth/providers/google', () => provider, { virtual: true })
jest.mock('next-auth/providers/github', () => provider, { virtual: true })
jest.mock('next-auth/providers/credentials', () => provider, { virtual: true })
jest.mock('@/lib/db', () => ({ __esModule: true, default: { stubClient: true } }))
jest.mock('@/lib/api-token', () => ({ mintApiToken: jest.fn(() => 'minted.api.jwt') }))

type Callbacks = {
  jwt: (args: Record<string, unknown>) => Promise<Record<string, unknown>>
  session: (args: Record<string, unknown>) => Promise<Record<string, unknown>>
}

function loadCallbacks(): Callbacks {
  jest.isolateModules(() => {
    require('@/auth')
  })
  return (captured.config as { callbacks: Callbacks }).callbacks
}

describe('auth.ts token exposure', () => {
  it('the jwt callback does not persist the provider access token', async () => {
    const { jwt } = loadCallbacks()
    const token = await jwt({
      token: { email: 'a@example.com' },
      user: { id: 'user_1' },
      account: { provider: 'google', access_token: 'ya29.provider-secret' },
      isNewUser: false,
    })
    expect(token.id).toBe('user_1')
    expect(JSON.stringify(token)).not.toContain('ya29.provider-secret')
    expect(token).not.toHaveProperty('accessToken')
  })

  it('the jwt callback strips a legacy provider token from an existing session', async () => {
    // A cookie issued before #527: no `account`, token already holds the claim.
    const { jwt } = loadCallbacks()
    const token = await jwt({
      token: { id: 'user_1', email: 'a@example.com', accessToken: 'ya29.legacy', access_token: 'ya29.legacy2' },
    })
    expect(token.id).toBe('user_1')
    expect(token).not.toHaveProperty('accessToken')
    expect(token).not.toHaveProperty('access_token')
    expect(JSON.stringify(token)).not.toContain('ya29.')
  })

  it('the session callback exposes apiToken and has no accessToken field', async () => {
    const { session } = loadCallbacks()
    const result = await session({
      session: { user: { name: 'A', email: 'a@example.com' } },
      token: { id: 'user_1', email: 'a@example.com', accessToken: 'ya29.leftover-from-old-jwt' },
    })
    expect(result.apiToken).toBe('minted.api.jwt')
    expect(result).not.toHaveProperty('accessToken')
    expect(JSON.stringify(result)).not.toContain('ya29.')
  })
})
