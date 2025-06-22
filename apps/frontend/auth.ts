// frontend/auth.ts

import NextAuth from "next-auth"
import { MongoDBAdapter } from "@auth/mongodb-adapter"
import GoogleProvider from "next-auth/providers/google"
import GitHubProvider from "next-auth/providers/github"
import CredentialsProvider from "next-auth/providers/credentials"
import client from "./app/lib/db"

// Development mode flag
const isDevelopment = process.env.NODE_ENV === 'development'
const skipAuth = process.env.SKIP_AUTH === 'true'

const providers = []

// Add dev-only credentials provider for bypassing auth
if (isDevelopment && skipAuth) {
  providers.push(
    CredentialsProvider({
      name: 'Development',
      credentials: {
        email: { label: "Email", type: "email", placeholder: "dev@example.com" }
      },
      async authorize(credentials) {
        // In dev mode with SKIP_AUTH=true, accept any email
        if (credentials?.email) {
          return {
            id: 'dev-user-' + credentials.email.split('@')[0],
            email: credentials.email,
            name: credentials.email.split('@')[0],
            image: null,
          }
        }
        return null
      }
    })
  )
}

// Always add OAuth providers
providers.push(
  GoogleProvider({
    clientId: process.env.GOOGLE_CLIENT_ID || 'dummy-client-id',
    clientSecret: process.env.GOOGLE_CLIENT_SECRET || 'dummy-client-secret',
  }),
  GitHubProvider({
    clientId: process.env.GITHUB_ID || 'dummy-client-id',
    clientSecret: process.env.GITHUB_SECRET || 'dummy-client-secret',
  })
)
 
export const { handlers, signIn, signOut, auth } = NextAuth({
  adapter: skipAuth ? undefined : MongoDBAdapter(client),
  providers,
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user, account }) {
      // Initial sign in
      if (account && user) {
        return {
          ...token,
          id: user.id,
          accessToken: account.access_token,
        }
      }
      
      // Return previous token if the access token has not expired yet
      return token
    },
    async session({ session, token }) {
      if (session?.user) {
        session.user.id = token.id as string
      }
      // Add the JWT token to the session so we can pass it to the backend
      session.accessToken = token.accessToken
      return session
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: '/auth/signin',
    error: '/auth/error',
  },
})
