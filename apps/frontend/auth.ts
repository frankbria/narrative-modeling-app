// frontend/auth.ts

import NextAuth from "next-auth"
import { MongoDBAdapter } from "@auth/mongodb-adapter"
import GoogleProvider from "next-auth/providers/google"
import GitHubProvider from "next-auth/providers/github"
import CredentialsProvider from "next-auth/providers/credentials"
import client from "./lib/db"
import { mintApiToken } from "./lib/api-token"
import { isSignInAllowed } from "./lib/invite-allowlist"
import { assertAuthConfig } from "./lib/auth-config"

// Fail fast (issue #271): in production, refuse to start when OAuth creds or
// NEXTAUTH_SECRET are missing instead of silently running with dummy/weak auth.
// No-op in development/test, where the dummy fallbacks below are intentional.
assertAuthConfig()

// Development mode flag
const isDevelopment = process.env.NODE_ENV === 'development'

const providers = []

// Add credentials provider for E2E testing and development
// This allows test users to authenticate without OAuth
if (isDevelopment || process.env.NODE_ENV === 'test') {
  providers.push(
    CredentialsProvider({
      id: 'credentials',
      name: 'Test User',
      credentials: {
        email: { label: "Email", type: "email", placeholder: "test@example.com" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        // Accept specific test user credentials
        const testEmail = process.env.TEST_USER_EMAIL || 'test@narrativeml.com'
        const testPassword = process.env.TEST_USER_PASSWORD || 'test-password-123'

        if (
          credentials?.email === testEmail &&
          credentials?.password === testPassword
        ) {
          return {
            id: 'test-user-12345',
            email: testEmail,
            name: 'Test User',
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
  adapter: MongoDBAdapter(client),
  providers,
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user, account, isNewUser }) {
      // Initial sign in
      if (account && user) {
        return {
          ...token,
          id: user.id,
          accessToken: account.access_token,
          isNewUser: isNewUser, // Track if this is a new user
        }
      }
      
      // Return previous token if the access token has not expired yet
      return token
    },
    async session({ session, token }) {
      if (session?.user) {
        session.user.id = token.id as string
      }
      // Keep the OAuth provider access token (legacy field).
      session.accessToken = token.accessToken as string | undefined
      // Mint a backend-verifiable HS256 JWT (sub=userId) so API calls
      // authenticate under SKIP_AUTH=false. Best-effort: a missing secret
      // must not crash session reads (the backend then returns 401).
      if (token.id) {
        try {
          // Carry the email claim so the backend can mirror the invite gate.
          session.apiToken = mintApiToken(
            token.id as string,
            token.email as string | null | undefined,
          )
        } catch (err) {
          // Don't crash session reads, but surface the cause — otherwise a
          // misconfigured secret silently 401s every API call with no signal.
          console.error('[auth] mintApiToken failed:', err)
          session.apiToken = undefined
        }
      }
      return session
    },
    async signIn({ user, account }) {
      // Invite-only beta gate (issue #261). Runs server-side in NextAuth, so a
      // rejected user never gets a session or a minted API token — the primary
      // control; the FastAPI backend mirrors it as defense-in-depth. Returning
      // false redirects to /auth/error?error=AccessDenied (see that page for
      // the "request access" message). An empty INVITE_ALLOWLIST disables the
      // gate (dev/test/un-configured deploys).
      //
      // The credentials provider self-attests its email and is registered only
      // in dev/test (see providers above), so it must never satisfy the email
      // gate: when the allowlist is active, only federated OAuth sign-ins pass.
      // The test user still signs in locally where INVITE_ALLOWLIST is unset.
      return isSignInAllowed(account?.provider, user?.email)
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: '/auth/signin',
    signOut: '/auth/signout',
    verifyRequest: '/auth/verify-request',
    newUser: '/auth/new-user', // New users will be directed here after signing in
    error: '/auth/error',
  },
})
