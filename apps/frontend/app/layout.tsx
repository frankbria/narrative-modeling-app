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
            <main className="flex-1 p-4 bg-gray-100 min-h-screen flex flex-col items-center justify-center space-y-6">
                <p className="text-xl text-gray-900">
                Please sign in below in order to access the application.
                </p>
                <SignInButton mode="modal">
                <button className="px-6 py-3 text-white text-lg font-semibold rounded-2xl bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300">
                    Sign In
                </button>
                </SignInButton>
            </main>
            </SignedOut>
        </body>
      </html>
    </ClerkProvider>
  )
}
