// apps/frontend/app/layout.tsx

import './globals.css'
import './animations.css'
import { type Metadata } from 'next'
import { auth } from '../auth'
import SessionProvider from '@/components/SessionProvider'
import { ThemeProvider } from '@/components/ThemeProvider'
import SidebarWrapper from '@/components/SidebarWrapper'
import ConditionalAIChat from '@/components/ConditionalAIChat'
import { WorkflowProvider } from '@/lib/contexts/WorkflowContext'
import { WorkflowBar } from '@/components/WorkflowBar'
import { StageGuardBanner } from '@/components/workflow/StageGuardBanner'
import { FeedbackWidget } from '@/components/FeedbackWidget'
import { SourceOffer } from '@/components/SourceOffer'

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
    // suppressHydrationWarning: next-themes writes the resolved class onto <html>
    // in a pre-hydration script, so the server markup and the first client render
    // legitimately differ on this one attribute (#407).
    <html lang="en" suppressHydrationWarning>
      <body className={`flex antialiased`}>
        {/* Skip-to-content link — first focusable element, visible only on focus
            so keyboard users can bypass the nav (WCAG 2.4.1 / issue #282). */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-white focus:shadow-lg"
        >
          Skip to main content
        </a>
        <ThemeProvider>
        <SessionProvider session={session}>
          <WorkflowProvider>
            {session ? (
              <>
                <SidebarWrapper />
                {/* min-w-0: as a flex item of <body>, main's default min-width:auto would
                    adopt the WorkflowBar's intrinsic width and force whole-page horizontal
                    scroll on narrow viewports instead of letting the stage strip scroll (#185) */}
                <main className="flex flex-1 min-w-0 min-h-screen flex-col">
                  <WorkflowBar />
                  <StageGuardBanner />
                  <div className="flex flex-1">
                    {/* Sidebar/chat are `fixed`; reserve their gutters only at lg+
                        where they're pinned. Below lg the sidebar is a drawer and
                        content is full-width (issue #282). */}
                    <div
                      id="main-content"
                      tabIndex={-1}
                      className="flex-1 p-4 bg-muted lg:ml-64 lg:mr-80 focus:outline-none"
                    >
                      {children}
                    </div>
                    <ConditionalAIChat />
                  </div>
                </main>
                <FeedbackWidget />
              </>
            ) : (
              <main
                id="main-content"
                tabIndex={-1}
                className="flex-1 p-4 bg-muted min-h-screen flex flex-col items-center justify-center space-y-6 focus:outline-none"
              >
                {children}
              </main>
            )}
            {/* AGPL-3.0 §13: source offer visible to all network users,
                authenticated or not. */}
            <SourceOffer />
          </WorkflowProvider>
        </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
