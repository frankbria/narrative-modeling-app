import { NextResponse } from 'next/server'
import { OpenAI } from 'openai'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

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
    const { message, context, messageHistory = [] } = await request.json()

    // Construct the messages array with system prompt, context, and history
    const messages = [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'system', content: `Dataset Context: ${context}` },
      ...messageHistory,
      { role: 'user', content: message }
    ]

    const response = await openai.chat.completions.create({
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