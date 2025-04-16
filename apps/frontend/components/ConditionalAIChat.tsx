'use client'

import { usePathname } from 'next/navigation'
import { AIChat } from './AIChat'

export default function ConditionalAIChat() {
  const pathname = usePathname()
  
  // Show AIChat on both review and explore pages
  if (pathname === '/review' || pathname === '/explore') {
    return <AIChat />
  }
  
  return null
} 