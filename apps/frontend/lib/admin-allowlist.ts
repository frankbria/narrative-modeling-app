// frontend/lib/admin-allowlist.ts
//
// Admin allowlist (issue #477).
//
// The app has no admin role anywhere — /admin was reachable by every signed-in
// tenant because the middleware only checks *authentication*. The smallest
// sufficient concept is an env allowlist of admin emails (`ADMIN_EMAILS`,
// comma-separated), checked server-side: in middleware.ts for the /admin route
// and in the NextAuth session callback to expose `session.isAdmin` to the UI.
//
// Unlike the invite gate (lib/invite-allowlist.ts), an EMPTY / unset list FAILS
// CLOSED: nobody is an admin. "Not configured" must never mean "everyone is".

import { parseAllowlist } from './invite-allowlist';

/**
 * True if `email` is on the admin allowlist (case-insensitive, trimmed).
 *
 * @param raw defaults to `process.env.ADMIN_EMAILS` (injectable for tests).
 */
export function isAdminEmail(
  email: string | null | undefined,
  raw: string | undefined | null = process.env.ADMIN_EMAILS,
): boolean {
  if (!email) return false;
  return parseAllowlist(raw).has(email.trim().toLowerCase());
}
