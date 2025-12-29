// apps/frontend/app/layout.tsx

import './globals.css'
import './animations.css'
import { type Metadata } from 'next'
import { auth } from '../auth'
import SessionProvider from '@/components/SessionProvider'
import SidebarWrapper from '@/components/SidebarWrapper'
import ConditionalAIChat from '@/components/ConditionalAIChat'
import { WorkflowProvider } from '@/lib/contexts/WorkflowContext'
import { WorkflowBar } from '@/components/WorkflowBar'

export const metadata: Metadata = {
  title: 'Narrative Modeling App',
  description: 'Build and deploy machine learning models with ease.',
  icons: {
    icon: [
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon.ico', sizes: 'any', type: 'image/x-icon' },
    ],
    apple: '/apple-touch-icon.png',
  },
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Get the authenticated session
  const session = await auth();

  return (
    <html lang="en">
      <body className={`flex antialiased`}>
        <SessionProvider session={session}>
          <WorkflowProvider>
            {session ? (
              <>
                <SidebarWrapper />
                <main className="flex flex-1 min-h-screen flex-col">
                  <WorkflowBar />
                  <div className="flex flex-1">
                    <div className="flex-1 p-4 bg-gray-100 ml-64 mr-80">{children}</div>
                    <ConditionalAIChat />
                  </div>
                </main>
              </>
            ) : (
              <main className="flex-1 p-4 bg-gray-100 min-h-screen flex flex-col items-center justify-center space-y-6">
                {children}
              </main>
            )}
          </WorkflowProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
