import { NextResponse } from 'next/server'
import { OpenAI } from 'openai'
import { auth } from '@/auth'
import { rateLimit } from '@/lib/api-guards'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

// Per-user throttle for the OpenAI proxy (guards against cost amplification).
const CHAT_RATE_LIMIT = { limit: 20, windowMs: 60_000 }

// Lazily constructed: the OpenAI SDK throws when apiKey is undefined, which
// breaks `next build` page-data collection in environments without secrets
// (e.g. Docker image builds).
let openaiClient: OpenAI | null = null
function getOpenAI(): OpenAI {
  if (!openaiClient) {
    openaiClient = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    })
  }
  return openaiClient
}

const model = process.env.OPENAI_MODEL || 'gpt-3.5-turbo'

// Initial system prompt to guide the AI's behavior
const SYSTEM_PROMPT = `You are an AI data analysis assistant. Your primary goal is to help users understand and analyze their datasets.

When responding to questions:
1. Rely primarily on the dataset context provided by the user for specific recommendations and insights
2. Use your general knowledge only for providing context and explaining concepts
3. Be clear about which insights come from the dataset vs. general knowledge
4. If asked about something not covered in the dataset, acknowledge this limitation
5. Maintain a helpful and professional tone
6. Keep responses concise and focused on the user's question

Remember: Your main value is in helping users understand their specific data, not in providing general information.`

export async function POST(request: Request) {
  try {
    // Require an authenticated session — this route is a paid OpenAI proxy.
    const session = await auth()
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Throttle per user to prevent cost-amplification abuse.
    const limit = rateLimit(`chat:${session.user.id}`, CHAT_RATE_LIMIT)
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Too many requests' },
        { status: 429, headers: { 'Retry-After': String(Math.ceil(limit.retryAfterMs / 1000)) } }
      )
    }

    const { message, context, messageHistory = [] } = await request.json()

    // Construct the messages array with system prompt, context, and history
    const messages = [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'system', content: `Dataset Context: ${context}` },
      ...messageHistory,
      { role: 'user', content: message }
    ]

    const response = await getOpenAI().chat.completions.create({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 1000,
    })

    const reply = response.choices[0]?.message?.content || ''
    return NextResponse.json({ reply })
  } catch (error: unknown) {
    console.error('OpenAI Error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'An error occurred' },
      { status: 500 }
    )
  }
} 