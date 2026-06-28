import { getSession } from 'next-auth/react';

/**
 * Return the backend-verifiable API token for the current session.
 *
 * The token is an HS256 JWT (sub=userId) minted server-side in the NextAuth
 * `session` callback (see auth.ts -> lib/api-token.ts) and signed with
 * NEXTAUTH_SECRET, which the FastAPI backend validates. Returns null when there
 * is no session or the token could not be minted.
 */
export async function getAuthToken() {
  const session = await getSession();
  return session?.apiToken ?? null;
}