// frontend/auth.ts

import NextAuth from "next-auth"
import { MongoDBAdapter } from "@auth/mongodb-adapter"
import GoogleProvider from "next-auth/providers/google"
import GitHubProvider from "next-auth/providers/github"
import CredentialsProvider from "next-auth/providers/credentials"
import client from "./lib/db"
import { mintApiToken } from "./lib/api-token"
import { isSignInAllowed, signupMode } from "./lib/invite-allowlist"
import { isAdminEmail } from "./lib/admin-allowlist"
import { assertAuthConfig, assertDatabaseConfig } from "./lib/auth-config"
import { resolveTestAdmin } from "./lib/test-credentials"
import { recordAccountCreated } from "./lib/product-events"

// Fail fast (issue #271): in production, refuse to start when OAuth creds or
// NEXTAUTH_SECRET are missing instead of silently running with dummy/weak auth.
// No-op in development/test, where the dummy fallbacks below are intentional.
assertAuthConfig()
assertDatabaseConfig()
// SIGNUP_MODE=open is a deliberate value (#768), so say it out loud at startup.
if (signupMode() === 'open' && process.env.NODE_ENV === 'production') {
  console.warn('[auth] Signup mode: OPEN — any Google/GitHub account may sign up (SIGNUP_MODE=open)')
}

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
        // Second dev/test identity (#613): an admin for the /admin smoke spec,
        // present only when TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD are both set.
        return resolveTestAdmin(
          typeof credentials?.email === 'string' ? credentials.email : undefined,
          typeof credentials?.password === 'string' ? credentials.password : undefined,
        )
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
  // Name the database explicitly, matching the backend convention (bare
  // MONGODB_URI + separate MONGODB_DB, see main.py's `client[db_name]`).
  // Without this the adapter calls `client.db(undefined)`, which falls back to
  // the URI's default database — and to `test` when the URI has no path at all.
  // Undefined here reproduces exactly that old behaviour, so environments that
  // still carry the database in the URI are unaffected.
  adapter: MongoDBAdapter(client, { databaseName: process.env.MONGODB_DB }),
  providers,
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user, account, isNewUser }) {
      // Initial sign in
      if (account && user) {
        // Deliberately NOT persisting account.access_token: that is the OAuth
        // provider's credential. Nothing here calls Google/GitHub on the user's
        // behalf, and exposing it to the browser led to it being forwarded to
        // our own backend as the bearer (#527).
        return {
          ...token,
          id: user.id,
          isNewUser: isNewUser, // Track if this is a new user
        }
      }
      
      // Existing sessions: a JWT issued before #527 still carries the provider
      // access token as a claim, and this path used to return it untouched until
      // the cookie expired. Strip it on every read so the cleanup is not gated on
      // a re-login (codex review).
      const { accessToken: _legacy, access_token: _legacySnake, ...rest } = token as Record<string, unknown>
      void _legacy
      void _legacySnake
      return rest
    },
    async session({ session, token }) {
      if (session?.user) {
        session.user.id = token.id as string
      }
      // Server-computed admin flag (issue #477): the client cannot read
      // ADMIN_EMAILS, so the sidebar shows the Admin link from this. It is UX
      // only — middleware.ts guards the /admin route independently.
      session.isAdmin = isAdminEmail(token.email)
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
      // Signup gate (#261, #768). Runs server-side in NextAuth, so a rejected
      // user never gets a session or a minted API token — the primary control;
      // the FastAPI backend mirrors it as defense-in-depth. Returning false
      // redirects to /auth/error?error=AccessDenied. SIGNUP_MODE decides:
      // `open` admits everyone, `invite` only INVITE_ALLOWLIST emails; unset in
      // production is `invite` (see lib/invite-allowlist.ts).
      return isSignInAllowed(account?.provider, user?.email)
    },
  },
  events: {
    // Funnel telemetry (#769): the only server-side moment that knows an account
    // was just created. Best-effort; see lib/product-events.ts.
    async createUser({ user }) {
      if (user.id) await recordAccountCreated(client, user.id)
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: '/auth/signin',
    signOut: '/auth/signout',
    newUser: '/auth/new-user', // New users will be directed here after signing in
    error: '/auth/error',
  },
})
