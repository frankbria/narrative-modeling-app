import path from 'path';

/**
 * E2E users that belong to one spec each (#743).
 *
 * Every other spec is the shared test user, so a spec that changes account-scoped
 * state (onboarding progress, an account erase) used to change what the rest
 * started from. A spec that does so runs as its own user instead:
 *
 *   test.use({ storageState: isolatedState('onboarding') });
 *
 * and every fixture (`page`, `request`, `authenticatedPage`, `trainModel`) is then
 * that user. global-setup signs each one in; `test-e2e.sh` turns the identities on
 * (`TEST_ISOLATED_USERS=1`, read by lib/test-credentials.ts).
 *
 * shortcut: one account per name, not per Playwright project, so two projects in one
 * invocation run these specs as the same account at the same time. Every script pins
 * one Chromium project; key the name by `testInfo.project.name` if one stops doing so.
 */
export const ISOLATED_USERS = ['onboarding', 'erasure'] as const;
export type IsolatedUser = (typeof ISOLATED_USERS)[number];

/** `local+slug@domain` of the shared test user's address. */
export function isolatedEmail(user: IsolatedUser): string {
  const base = process.env.TEST_USER_EMAIL || 'test@narrativeml.com';
  const at = base.lastIndexOf('@');
  return `${base.slice(0, at)}+${user}${base.slice(at)}`;
}

export function isolatedState(user: IsolatedUser): string {
  return path.join(__dirname, '.auth', `${user}.json`);
}
