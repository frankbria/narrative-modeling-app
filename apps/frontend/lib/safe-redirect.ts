// frontend/lib/safe-redirect.ts
//
// Open-redirect guard for post-sign-in navigation (issue #271).
//
// The sign-in page reads `?callbackUrl=...` and both `router.push()`es it and
// hands it to NextAuth `signIn()`. An attacker-supplied absolute URL
// (`?callbackUrl=https://evil.example`) would then redirect an authenticated
// user off-site — a phishing aid. Only accept root-relative same-origin paths.

/**
 * Return `raw` iff it is a safe root-relative path, else `fallback`.
 *
 * Accepts only a single leading `/` (root-relative). Rejects absolute URLs
 * (scheme), protocol-relative `//host`, and backslash tricks that browsers
 * normalize to `//` — all of which can escape the current origin.
 */
export function sanitizeCallbackUrl(
  raw: string | null | undefined,
  fallback = '/upload',
): string {
  if (!raw || typeof raw !== 'string') return fallback;
  if (raw[0] !== '/') return fallback; // must be root-relative (rejects scheme, bare paths, leading whitespace)
  if (raw[1] === '/') return fallback; // reject protocol-relative //host
  if (raw.includes('\\')) return fallback; // reject backslash (browser-normalized to '/')
  return raw;
}
