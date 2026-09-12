import { NextResponse } from 'next/server'
import { auth } from '@/auth'
import { rateLimit } from '@/lib/api-guards'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// Per-user throttle for the chat proxy (guards against cost amplification).
const CHAT_RATE_LIMIT = { limit: 20, windowMs: 60_000 }

// #461: this proxy no longer talks to OpenAI. The call happens in the backend behind
// the `ai_calls` quota (POST /ai/chat); the bounds here only fail fast — the backend
// enforces the same ones with 422.
const MAX_MESSAGE_CHARS = 4_000
const MAX_CONTEXT_CHARS = 8_000
const MAX_HISTORY_TURNS = 20
const MAX_TOTAL_CHARS = 24_000
const HISTORY_ROLES = new Set(['user', 'assistant'])

type Turn = { role: 'user' | 'assistant'; content: string }

/** Validate + rebuild the client payload; null when any bound is broken. */
function boundedInput(body: unknown): { message: string; context: string; history: Turn[] } | null {
  if (typeof body !== 'object' || body === null) return null
  const { message, context, messageHistory = [] } = body as Record<string, unknown>
  if (typeof message !== 'string' || message.length === 0 || message.length > MAX_MESSAGE_CHARS) return null
  if (typeof context !== 'string' || context.length > MAX_CONTEXT_CHARS) return null
  if (!Array.isArray(messageHistory) || messageHistory.length > MAX_HISTORY_TURNS) return null
  const history: Turn[] = []
  for (const t of messageHistory) {
    const role = (t as Record<string, unknown>)?.role
    const content = (t as Record<string, unknown>)?.content
    if (typeof role !== 'string' || !HISTORY_ROLES.has(role)) return null
    if (typeof content !== 'string' || content.length > MAX_MESSAGE_CHARS) return null
    history.push({ role: role as Turn['role'], content }) // role/content only — nothing else is forwarded
  }
  const total = message.length + context.length + history.reduce((n, t) => n + t.content.length, 0)
  if (total > MAX_TOTAL_CHARS) return null
  return { message, context, history }
}

export async function POST(request: Request) {
  try {
    // The backend accepts exactly one credential: the minted API JWT (#527).
    const session = await auth()
    const apiToken = session?.apiToken
    if (!session?.user?.id || !apiToken) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const limit = rateLimit(`chat:${session.user.id}`, CHAT_RATE_LIMIT)
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Too many requests' },
        { status: 429, headers: { 'Retry-After': String(Math.ceil(limit.retryAfterMs / 1000)) } }
      )
    }

    const input = boundedInput(await request.json().catch(() => null))
    if (!input) {
      return NextResponse.json({ error: 'Request exceeds the chat size limits' }, { status: 400 })
    }

    const upstream = await fetch(`${API_URL}/ai/chat`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    })
    if (!upstream.ok) {
      // 402 = plan limit reached; the status passes through so the UI can say so.
      const error = upstream.status === 402 ? 'AI call limit reached for your plan' : 'AI service unavailable'
      return NextResponse.json({ error }, { status: upstream.status })
    }
    const { reply } = await upstream.json()
    return NextResponse.json({ reply })
  } catch (error: unknown) {
    // Log detail server-side; return a generic message (issue #269).
    console.error('Chat proxy error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
