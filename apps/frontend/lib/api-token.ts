import { createHmac } from 'node:crypto';

// API token lifetime (seconds). Short-lived so a leaked token expires quickly;
// the NextAuth session callback re-mints it on every session read, so the
// client always holds a fresh one.
const API_TOKEN_TTL_SECONDS = 60 * 60;

function base64url(input: string): string {
  return Buffer.from(input, 'utf8').toString('base64url');
}

/**
 * Mint a backend-verifiable API token for the given user.
 *
 * Produces a standard HS256 JWT signed with NEXTAUTH_SECRET carrying the user
 * id as `sub`. The FastAPI backend (`app/auth/nextauth_auth.py`) decodes
 * exactly this (`jwt.decode(..., algorithms=["HS256"])`, reads `sub`), so no
 * backend change is needed — it replaces the old placeholder `nextauth-${id}`
 * string that the backend rejected under SKIP_AUTH=false.
 *
 * Runs only in the Node runtime (the NextAuth config is Node-only via the
 * MongoDB adapter), so `node:crypto` is available — no extra dependency.
 */
export function mintApiToken(userId: string): string {
  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    throw new Error('NEXTAUTH_SECRET is not set; cannot mint API token');
  }
  const now = Math.floor(Date.now() / 1000);
  const header = base64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = base64url(
    JSON.stringify({ sub: userId, iat: now, exp: now + API_TOKEN_TTL_SECONDS }),
  );
  const signingInput = `${header}.${payload}`;
  const signature = createHmac('sha256', secret).update(signingInput).digest('base64url');
  return `${signingInput}.${signature}`;
}
