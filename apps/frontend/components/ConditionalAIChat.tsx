'use client'

import { usePathname } from 'next/navigation'
import { AIChat } from './AIChat'

export default function ConditionalAIChat() {
  const pathname = usePathname()
  
  // Only show AIChat on the review page
  if (pathname === '/review') {
    return <AIChat />
  }
  
  return null
} 