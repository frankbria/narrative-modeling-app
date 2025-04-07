// apps/frontend/pages/api/chat.ts

import type { NextApiRequest, NextApiResponse } from 'next'
import { OpenAI } from 'openai'

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

const model = process.env.OPENAI_MODEL || 'gpt-3.5-turbo'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { message } = req.body

  try {
    const response = await openai.chat.completions.create({
      model,
      messages: [{ role: 'user', content: message }],
    })

    const reply = response.choices[0]?.message?.content || ''
    res.status(200).json({ reply })
  } catch (error: unknown) {
    if (error instanceof Error) {
      console.error('OpenAI Error:', error.message)
    } else {
      console.error('Unknown OpenAI Error:', error)
    }
  }
}
