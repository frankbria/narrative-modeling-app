// frontend/lib/health/readiness.ts
//
// What the frontend shares with the backend, checked the way a request would use it
// (#756). A stale MONGODB_URI or NEXTAUTH_SECRET in this container breaks sign-in
// while every page still renders, and the staging probe only looked at the backend.
//
// Every status is `healthy` or `unhealthy (<reason>)`. A reason is an error's class
// (and Mongo's code name) or a fixed phrase, never its message: the report lands in
// a public issue, and a Mongo error names the cluster.
import { MongoClient } from 'mongodb';
import { mintApiToken } from '@/lib/api-token';

type Env = Record<string, string | undefined>;
type Fetcher = typeof fetch;

export interface ReadinessReport {
  status: 'healthy' | 'unhealthy';
  checks: { mongo: string; api_token: string };
}

const TIMEOUT_MS = 8000;
const PROBE_USER = 'frontend-health-probe';

function unhealthy(reason: string): string {
  return `unhealthy (${reason})`;
}

/** `MongoServerError AuthenticationFailed`: the class, and Mongo's own code name when it is a plain word. */
function errorKind(error: unknown): string {
  const name = error instanceof Error ? error.constructor.name : 'Error';
  const codeName = (error as { codeName?: unknown }).codeName;
  const plain = typeof codeName === 'string' && /^[A-Za-z]+$/.test(codeName);
  return plain ? `${name} ${codeName}` : name;
}

/**
 * A NEW connection with this process's MONGODB_URI, and a ping of MONGODB_DB. The
 * adapter's own pool stays authenticated after the credential is rotated, so only a
 * fresh connection sees a stale value (the backend probe does the same, #552).
 */
export async function checkMongo(env: Env = process.env): Promise<string> {
  const uri = env.MONGODB_URI;
  if (!uri) return unhealthy('MONGODB_URI is not set');
  const client = new MongoClient(uri, { serverSelectionTimeoutMS: TIMEOUT_MS, connectTimeoutMS: TIMEOUT_MS });
  try {
    await client.connect();
    await client.db(env.MONGODB_DB).command({ ping: 1 });
    return 'healthy';
  } catch (error) {
    return unhealthy(errorKind(error));
  } finally {
    await client.close().catch(() => undefined);
  }
}

// The two answers that can only come after the backend verified the signature: the
// list itself, or the invite gate refusing a probe user who is on no allowlist.
const SIGNATURE_ACCEPTED = [200, 403];

/** What the backend's answer to a signed request says about the shared secret. */
function secretVerdict(status: number): string {
  if (SIGNATURE_ACCEPTED.includes(status)) return 'healthy';
  if (status === 401) return unhealthy('the backend rejected a token signed with this NEXTAUTH_SECRET');
  // A 404, a 5xx, a proxy's page: the request never reached the check, so it proves nothing.
  return unhealthy(`the backend answered ${status}`);
}

/**
 * A token minted the way the session callback mints one, sent to the backend. The
 * backend verifies it with ITS NEXTAUTH_SECRET, so a 401 means the two halves
 * disagree. The request is a read of an empty list for a user who owns nothing.
 */
export async function checkApiToken(env: Env = process.env, fetcher: Fetcher = fetch): Promise<string> {
  if (!env.NEXTAUTH_SECRET) return unhealthy('NEXTAUTH_SECRET is not set');
  if (!env.NEXT_PUBLIC_API_URL) return unhealthy('NEXT_PUBLIC_API_URL is not set');
  try {
    const response = await fetcher(`${env.NEXT_PUBLIC_API_URL}/datasets?page=1&limit=1`, {
      headers: { Authorization: `Bearer ${mintApiToken(PROBE_USER, null, env.NEXTAUTH_SECRET)}` },
      cache: 'no-store',
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return secretVerdict(response.status);
  } catch (error) {
    return unhealthy(errorKind(error));
  }
}

export async function readiness(env: Env = process.env, fetcher: Fetcher = fetch): Promise<ReadinessReport> {
  const [mongo, api_token] = await Promise.all([checkMongo(env), checkApiToken(env, fetcher)]);
  const healthy = mongo === 'healthy' && api_token === 'healthy';
  return { status: healthy ? 'healthy' : 'unhealthy', checks: { mongo, api_token } };
}
