'use client'

import { useEffect, useRef, useState } from 'react'

export default function AIChat() {
  const [messages, setMessages] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  const sendMessage = async () => {
    if (!input.trim() || isSending) return

    const controller = new AbortController()
    controllerRef.current = controller
    setIsSending(true)

    setMessages((prev) => [...prev, `You: ${input}`])
    const messageToSend = input
    setInput('')

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageToSend }),
        signal: controller.signal,
      })

      const text = await res.text()
      console.log('🔍 Raw response from API:', text)

      const data = JSON.parse(text)
      setMessages((prev) => [...prev, `AI: ${data.reply}`])
    } catch (err) {
      console.error('💥 Error in sendMessage:', err)
      setMessages((prev) => [...prev, '⚠️ Error contacting AI'])
    } finally {
      setIsSending(false)
    }
  }

  useEffect(() => {
    return () => {
      if (controllerRef.current) {
        controllerRef.current.abort()
      }
    }
  }, [])

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
          disabled={isSending}
        />
        <button
          onClick={sendMessage}
          disabled={isSending}
          className="bg-blue-500 text-white px-3 py-1 rounded text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
