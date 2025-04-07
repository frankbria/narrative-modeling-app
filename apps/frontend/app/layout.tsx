// apps/frontend/app/layout.tsx
import './globals.css'
import { type Metadata } from 'next'
import { ClerkProvider, SignedIn, SignedOut, SignInButton } from '@clerk/nextjs'
import { Geist, Geist_Mono } from 'next/font/google'
import SidebarWrapper from '@/components/SidebarWrapper'

export const metadata: Metadata = {
  title: 'Narrative Modeling App',
  description: 'Build and deploy machine learning models with ease.',
}

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={`${geistSans.variable} ${geistMono.variable} flex antialiased`}>
          <SignedIn>
            <SidebarWrapper />
            <main className="flex-1 p-4 bg-gray-100 min-h-screen">{children}</main>
          </SignedIn>

          <SignedOut>
            {/* Optional: Full-screen sign-in fallback or redirect */}
            <main className="flex-1 p-4 bg-gray-100 min-h-screen flex items-center justify-center">
              <p className="text-xl text-gray-900">Please sign in to access the app.</p>
                <SignInButton mode="modal" />
            </main>
          </SignedOut>
        </body>
      </html>
    </ClerkProvider>
  )
}
