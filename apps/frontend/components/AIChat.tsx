'use client'

import { useState } from 'react'

export default function AIChat() {
  const [messages, setMessages] = useState<string[]>([])
  const [input, setInput] = useState('')

  const sendMessage = async () => {
  if (!input.trim()) return

  setMessages((prev) => [...prev, input])
  setInput('')

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: input }),
    })

    const text = await res.text() // 👈 get raw text first
    console.log('🔍 Raw response from API:', text) // 👈 log it out

    const data = JSON.parse(text) // try to parse
    setMessages((prev) => [...prev, data.reply])
  } catch (err) {
    console.error('💥 Error in sendMessage:', err)
    setMessages((prev) => [...prev, 'Error contacting AI'])
  }
}


  return (
    <div className="flex flex-col h-full p-4 border-l border-gray-300 w-80 bg-gray-300">
      <div className="flex-1 overflow-y-auto space-y-2 mb-4 text-black">
        {messages.map((msg, idx) => (
          <div key={idx} className="bg-white p-2 rounded shadow text-sm whitespace-pre-wrap">
            {msg}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          className="flex-1 rounded border px-2 py-1 text-sm bg-white text-black"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Type a message..."
        />
        <button
          onClick={sendMessage}
          className="bg-blue-500 text-white px-3 py-1 rounded text-sm"
        >
          Send
        </button>
      </div>
    </div>
  )
}
