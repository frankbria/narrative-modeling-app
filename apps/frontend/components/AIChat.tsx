'use client'

import { useState, useRef, useEffect } from 'react'
import { useDatasetChatContext } from '@/lib/hooks/useDatasetChatContext'
import { useUser } from '@clerk/nextjs'
import { Send, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export function AIChat() {
  const { user } = useUser()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPageLoading, setIsPageLoading] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const { contextString, isLoading: isContextLoading, error: contextError, isAvailable } = useDatasetChatContext(user?.id ?? null)
  const initialMessageSetRef = useRef(false)
  const contextUpdatedRef = useRef(false)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Simulate page loading for 2 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsPageLoading(false)
    }, 2000)
    
    return () => clearTimeout(timer)
  }, [])

  // Initialize chat with a welcome message when context is loaded
  useEffect(() => {
    // Don't set any messages while the page is loading
    if (isPageLoading) return;
    
    // Don't set messages if we're still loading the context
    if (isContextLoading) return;
    
    // Only set initial message once when context is loaded
    if (initialMessageSetRef.current) return;
    
    if (contextError) {
      setMessages([
        {
          role: 'assistant',
          content: `Hello! I'm your AI data analysis assistant. I noticed there was an issue loading your dataset analysis. 

${contextError}

You can still ask me questions about your data, but I may not have all the context about your dataset.

What would you like to know about your data?`
        }
      ]);
      initialMessageSetRef.current = true;
      return;
    }

    // Only show "no dataset" message if we're not loading and there's no context
    if (!contextString && !isAvailable) {
      setMessages([
        {
          role: 'assistant',
          content: `Hello! I'm your AI data analysis assistant. I don't see any dataset analysis available yet.

You can upload a dataset to get started, or you can ask me general questions about data analysis.

How can I help you today?`
        }
      ]);
      initialMessageSetRef.current = true;
      return;
    }

    // Show dataset context if available
    if (contextString && isAvailable) {
      setMessages([
        {
          role: 'assistant',
          content: `Hello! I'm your AI data analysis assistant. I've analyzed your dataset and can help you explore it further. 

Here's what I've found so far:
${contextString}

How can I help you analyze this data? You can ask me questions about:
- Specific patterns or trends
- Data quality issues
- Relationships between variables
- Suggestions for further analysis
- Or any other aspects of your dataset`
        }
      ]);
      initialMessageSetRef.current = true;
    }
  }, [contextString, isContextLoading, contextError, isPageLoading, isAvailable]);

  // Update messages when context changes after initial load
  useEffect(() => {
    // Skip if still loading or if initial message hasn't been set yet
    if (isPageLoading || isContextLoading || !initialMessageSetRef.current) return;
    
    // Only update if we have a new context and it's available
    if (contextString && isAvailable) {
      // Use a ref to track if we've already updated for this context
      if (!contextUpdatedRef.current) {
        // Update the first message with the new context
        setMessages(prev => {
          // Only update if the first message is from the assistant (welcome message)
          if (prev.length > 0 && prev[0].role === 'assistant') {
            return [
              {
                role: 'assistant',
                content: `Hello! I'm your AI data analysis assistant. I've analyzed your dataset and can help you explore it further. 

Here's what I've found so far:
${contextString}

How can I help you analyze this data? You can ask me questions about:
- Specific patterns or trends
- Data quality issues
- Relationships between variables
- Suggestions for further analysis
- Or any other aspects of your dataset`
              },
              ...prev.slice(1) // Keep all other messages
            ];
          }
          return prev;
        });
        
        // Mark that we've updated for this context
        contextUpdatedRef.current = true;
      }
    } else {
      // Reset the context updated flag when context is not available
      contextUpdatedRef.current = false;
    }
  }, [contextString, isAvailable, isContextLoading, isPageLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isSubmitting) return

    const newMessage: Message = { role: 'user', content: input }
    setMessages(prev => [...prev, newMessage])
    setInput('')
    setIsSubmitting(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          context: contextString || 'No dataset context available.'
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to get response from AI');
      }

      const data = await response.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch (error) {
      console.error('Error getting AI response:', error)
      
      let errorMessage = 'I apologize, but I encountered an error processing your request.';
      
      if (error instanceof Error) {
        if (error.message.includes('OpenAI')) {
          errorMessage = 'I apologize, but there was an issue connecting to the AI service. This might be due to rate limiting or a temporary service disruption. Please try again in a few minutes.';
        } else if (error.message.includes('network') || error.message.includes('fetch')) {
          errorMessage = 'I apologize, but there was a network error. Please check your internet connection and try again.';
        }
      }
      
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: errorMessage
      }])
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed top-0 right-0 h-screen w-80 bg-white border-l border-gray-200 flex flex-col z-10">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800">AI Assistant</h2>
      </div>
      
      <div 
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {isPageLoading ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-gray-600 text-center">Loading dataset analysis...</p>
          </div>
        ) : isContextLoading ? (
          <div className="flex flex-col items-center justify-center h-full space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-gray-600 text-center">Analyzing your dataset...</p>
          </div>
        ) : (
          <>
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            
            {isSubmitting && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg p-3 bg-gray-100 text-gray-800">
                  <div className="flex items-center space-x-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                    <span className="text-sm text-gray-500">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 text-gray-900 placeholder-gray-500"
            disabled={isContextLoading || isSubmitting || isPageLoading}
          />
          <button
            type="submit"
            className="p-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isContextLoading || isSubmitting || isPageLoading}
          >
            {isSubmitting ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            ) : (
              <Send size={20} />
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
