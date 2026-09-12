/**
 * Admin allowlist (issue #477).
 *
 * The one behaviour that differs from the invite gate is the empty-list case:
 * an unset `ADMIN_EMAILS` must make NOBODY an admin, not everybody.
 */

import { isAdminEmail } from '@/lib/admin-allowlist';

describe('isAdminEmail', () => {
  it('fails closed: an unset or blank list admits nobody', () => {
    expect(isAdminEmail('alice@example.com', undefined)).toBe(false);
    expect(isAdminEmail('alice@example.com', '')).toBe(false);
    expect(isAdminEmail('alice@example.com', '  ,  ')).toBe(false);
  });

  it('admits a listed email, case-insensitively and trimmed', () => {
    const raw = ' Alice@Example.com , bob@example.com ';
    expect(isAdminEmail('alice@example.com', raw)).toBe(true);
    expect(isAdminEmail('  BOB@example.com ', raw)).toBe(true);
  });

  it('rejects an unlisted, missing, or empty email', () => {
    const raw = 'alice@example.com';
    expect(isAdminEmail('mallory@example.com', raw)).toBe(false);
    expect(isAdminEmail(null, raw)).toBe(false);
    expect(isAdminEmail(undefined, raw)).toBe(false);
    expect(isAdminEmail('', raw)).toBe(false);
  });

  it('reads ADMIN_EMAILS from the environment by default', () => {
    const prev = process.env.ADMIN_EMAILS;
    try {
      process.env.ADMIN_EMAILS = 'root@example.com';
      expect(isAdminEmail('root@example.com')).toBe(true);
      expect(isAdminEmail('t@example.com')).toBe(false);
      delete process.env.ADMIN_EMAILS;
      expect(isAdminEmail('root@example.com')).toBe(false);
    } finally {
      if (prev === undefined) delete process.env.ADMIN_EMAILS;
      else process.env.ADMIN_EMAILS = prev;
    }
  });
});
