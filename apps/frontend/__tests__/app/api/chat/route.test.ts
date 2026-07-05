/**
 * @jest-environment node
 *
 * Guards the security additions to the OpenAI chat proxy (issue #253):
 * an auth() gate and a per-user rate limit. OpenAI is mocked so no network
 * call or API key is needed.
 */
import { auth } from '@/auth'
import { __resetRateLimits } from '@/lib/api-guards'

jest.mock('@/auth', () => ({ auth: jest.fn() }))

const mockCreate = jest.fn()
jest.mock('openai', () => ({
  OpenAI: jest.fn().mockImplementation(() => ({
    chat: { completions: { create: mockCreate } },
  })),
}))

import { POST } from '@/app/api/chat/route'

const mockAuth = auth as jest.MockedFunction<typeof auth>

function chatRequest(): Request {
  return new Request('http://localhost/api/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ message: 'hi', context: 'ctx', messageHistory: [] }),
  })
}

describe('POST /api/chat', () => {
  beforeEach(() => {
    __resetRateLimits()
    mockAuth.mockResolvedValue({ user: { id: 'test-user' } } as never)
    mockCreate.mockResolvedValue({ choices: [{ message: { content: 'reply' } }] })
  })

  it('returns 401 without a session and never calls OpenAI', async () => {
    mockAuth.mockResolvedValue(null as never)

    const res = await POST(chatRequest())
    expect(res.status).toBe(401)
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('returns 429 once the per-user limit is exceeded', async () => {
    // Limit is 20/min; the 21st request in the window is blocked.
    for (let i = 0; i < 20; i++) {
      expect((await POST(chatRequest())).status).toBe(200)
    }
    const blocked = await POST(chatRequest())
    expect(blocked.status).toBe(429)
    expect(blocked.headers.get('Retry-After')).toBeTruthy()
  })
})
