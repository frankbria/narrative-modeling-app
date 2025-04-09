import { NextResponse } from 'next/server'
import { OpenAI } from 'openai'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

const model = process.env.OPENAI_MODEL || 'gpt-3.5-turbo'

export async function POST(request: Request) {
  try {
    const { message } = await request.json()

    const response = await openai.chat.completions.create({
      model,
      messages: [{ role: 'user', content: message }],
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