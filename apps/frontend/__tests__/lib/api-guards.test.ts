import { rateLimit, __resetRateLimits } from '@/lib/api-guards'

describe('rateLimit', () => {
  beforeEach(() => __resetRateLimits())

  it('allows requests up to the limit, then blocks', () => {
    const opts = { limit: 3, windowMs: 1000, now: 1000 }
    expect(rateLimit('u1', opts).allowed).toBe(true)
    expect(rateLimit('u1', opts).allowed).toBe(true)
    expect(rateLimit('u1', opts).allowed).toBe(true)

    const blocked = rateLimit('u1', opts)
    expect(blocked.allowed).toBe(false)
    expect(blocked.remaining).toBe(0)
    expect(blocked.retryAfterMs).toBeGreaterThan(0)
  })

  it('tracks each key independently', () => {
    const opts = { limit: 1, windowMs: 1000, now: 5000 }
    expect(rateLimit('a', opts).allowed).toBe(true)
    expect(rateLimit('a', opts).allowed).toBe(false)
    // A different key still has its own fresh budget.
    expect(rateLimit('b', opts).allowed).toBe(true)
  })

  it('resets once the window has elapsed', () => {
    expect(rateLimit('u', { limit: 1, windowMs: 1000, now: 0 }).allowed).toBe(true)
    // Still inside the window → blocked.
    expect(rateLimit('u', { limit: 1, windowMs: 1000, now: 500 }).allowed).toBe(false)
    // Window elapsed → allowed again.
    expect(rateLimit('u', { limit: 1, windowMs: 1000, now: 1000 }).allowed).toBe(true)
  })
})
