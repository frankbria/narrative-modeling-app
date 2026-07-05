// lib/api-guards.ts
// Shared guards for Next.js API route handlers: a small in-memory rate limiter.

interface WindowState {
  count: number
  resetAt: number
}

// ponytail: in-memory per-instance limiter — counters reset on redeploy and are NOT
// shared across serverless/edge instances. Fine for throttling abuse from a single
// worker; swap this Map for Redis/Upstash if the frontend runs multi-instance and
// cross-instance limits start to matter.
const buckets = new Map<string, WindowState>()

export interface RateLimitOptions {
  /** Max requests allowed per window. */
  limit: number
  /** Window length in milliseconds. */
  windowMs: number
  /** Injectable clock for testing; defaults to Date.now(). */
  now?: number
}

export interface RateLimitResult {
  allowed: boolean
  remaining: number
  /** Milliseconds until the current window resets (0 when allowed with headroom). */
  retryAfterMs: number
}

/**
 * Fixed-window rate limit keyed by an arbitrary string (e.g. a user id).
 * Returns whether the request is allowed and how long to wait if not.
 */
export function rateLimit(key: string, options: RateLimitOptions): RateLimitResult {
  const { limit, windowMs } = options
  const now = options.now ?? Date.now()
  const state = buckets.get(key)

  // New key, or the previous window has elapsed → start a fresh window.
  if (!state || now >= state.resetAt) {
    buckets.set(key, { count: 1, resetAt: now + windowMs })
    return { allowed: true, remaining: limit - 1, retryAfterMs: 0 }
  }

  if (state.count >= limit) {
    return { allowed: false, remaining: 0, retryAfterMs: state.resetAt - now }
  }

  state.count += 1
  return { allowed: true, remaining: limit - state.count, retryAfterMs: 0 }
}

/** Test-only helper to clear all rate-limit state between cases. */
export function __resetRateLimits(): void {
  buckets.clear()
}
