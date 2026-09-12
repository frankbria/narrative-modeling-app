/**
 * @jest-environment node
 *
 * The preview proxy must forward the minted API JWT — never the OAuth provider
 * token and never a placeholder (#527). Before this fix it sent
 * `session.accessToken` (a Google/GitHub credential) and fell back to the literal
 * string "default" when that was absent.
 */
import { auth } from '@/auth'

jest.mock('@/auth', () => ({ auth: jest.fn() }))
jest.mock('next-auth/jwt', () => ({ getToken: jest.fn() }))

import { GET } from '@/app/api/data/[id]/preview/route'
import { getToken } from 'next-auth/jwt'

const mockAuth = auth as jest.MockedFunction<typeof auth>
const mockGetToken = getToken as jest.MockedFunction<typeof getToken>
const API_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEifQ.sig'

function previewRequest(query = '?rows=5&offset=10') {
  const req = new Request(`http://localhost/api/data/ds-1/preview${query}`)
  // NextRequest exposes nextUrl; the route reads searchParams from it.
  Object.defineProperty(req, 'nextUrl', { value: new URL(req.url) })
  return req as unknown as import('next/server').NextRequest
}

const params = Promise.resolve({ id: 'ds-1' })

describe('GET /api/data/[id]/preview', () => {
  let fetchMock: jest.Mock

  beforeEach(() => {
    fetchMock = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ rows: [] }), { status: 200 })
    )
    global.fetch = fetchMock as unknown as typeof fetch
    mockGetToken.mockReset()
  })

  it('forwards the minted API JWT as the bearer, not the provider token', async () => {
    mockAuth.mockResolvedValue({
      user: { id: 'user_1' },
      apiToken: API_TOKEN,
      accessToken: 'ya29.google-provider-token',
    } as never)

    const res = await GET(previewRequest(), { params })

    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/data/ds-1/preview?rows=5&offset=10')
    expect((init as RequestInit).headers).toMatchObject({ Authorization: `Bearer ${API_TOKEN}` })
    expect(JSON.stringify(init)).not.toContain('ya29.google-provider-token')
    expect(mockGetToken).not.toHaveBeenCalled()
  })

  it('returns 401 without a session and never calls the backend', async () => {
    mockAuth.mockResolvedValue(null as never)

    const res = await GET(previewRequest(), { params })

    expect(res.status).toBe(401)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns 401 when the session has no API token — never a placeholder bearer', async () => {
    mockAuth.mockResolvedValue({ user: { id: 'user_1' } } as never)

    const res = await GET(previewRequest(), { params })

    expect(res.status).toBe(401)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('passes the backend status through on failure', async () => {
    mockAuth.mockResolvedValue({ user: { id: 'user_1' }, apiToken: API_TOKEN } as never)
    fetchMock.mockResolvedValue(new Response('nope', { status: 404 }))

    const res = await GET(previewRequest(), { params })

    expect(res.status).toBe(404)
  })
})
