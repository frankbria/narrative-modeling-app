/**
 * Invite-only beta gate — allowlist logic (issue #261).
 *
 * Asserts the AC directly: a non-allowlisted email is denied and an
 * allowlisted one is admitted, plus the gate-disabled (empty list) default.
 */

import { parseAllowlist, isEmailAllowed, isSignInAllowed } from '@/lib/invite-allowlist';

describe('parseAllowlist', () => {
  it('returns an empty set for unset/empty input', () => {
    expect(parseAllowlist(undefined).size).toBe(0);
    expect(parseAllowlist('').size).toBe(0);
    expect(parseAllowlist('   ').size).toBe(0);
  });

  it('splits, trims, lowercases, and drops blanks', () => {
    const set = parseAllowlist(' Alice@Example.com , bob@example.com ,, ');
    expect(set.has('alice@example.com')).toBe(true);
    expect(set.has('bob@example.com')).toBe(true);
    expect(set.size).toBe(2);
  });
});

describe('isEmailAllowed', () => {
  const LIST = 'alice@example.com, bob@example.com';

  it('admits an allowlisted email (case-insensitive)', () => {
    expect(isEmailAllowed('alice@example.com', LIST)).toBe(true);
    expect(isEmailAllowed('ALICE@example.com', LIST)).toBe(true);
  });

  it('denies a non-allowlisted email', () => {
    expect(isEmailAllowed('eve@evil.com', LIST)).toBe(false);
  });

  it('denies a missing email when the gate is active', () => {
    expect(isEmailAllowed(null, LIST)).toBe(false);
    expect(isEmailAllowed(undefined, LIST)).toBe(false);
    expect(isEmailAllowed('', LIST)).toBe(false);
  });

  it('disables the gate (allows everyone) when the list is empty/unset', () => {
    expect(isEmailAllowed('eve@evil.com', '')).toBe(true);
    expect(isEmailAllowed('eve@evil.com', undefined)).toBe(true);
    expect(isEmailAllowed(null, '')).toBe(true);
  });

  it('reads process.env.INVITE_ALLOWLIST by default (email path)', () => {
    const prev = process.env.INVITE_ALLOWLIST;
    process.env.INVITE_ALLOWLIST = 'alice@example.com';
    try {
      expect(isEmailAllowed('alice@example.com')).toBe(true);
      expect(isEmailAllowed('eve@evil.com')).toBe(false);
    } finally {
      if (prev === undefined) delete process.env.INVITE_ALLOWLIST;
      else process.env.INVITE_ALLOWLIST = prev;
    }
  });
});

describe('isSignInAllowed', () => {
  const LIST = 'alice@example.com';

  it('checks OAuth sign-ins against the allowlist by email', () => {
    expect(isSignInAllowed('google', 'alice@example.com', LIST)).toBe(true);
    expect(isSignInAllowed('github', 'eve@evil.com', LIST)).toBe(false);
  });

  it('rejects the credentials provider when the gate is active, even with an allowlisted email', () => {
    // The credentials provider self-attests its email, so an allowlisted value
    // submitted through it must NOT pass while the gate is on.
    expect(isSignInAllowed('credentials', 'alice@example.com', LIST)).toBe(false);
  });

  it('allows the credentials provider when the gate is disabled (dev/test)', () => {
    expect(isSignInAllowed('credentials', 'test@narrativeml.com', '')).toBe(true);
    expect(isSignInAllowed('credentials', 'test@narrativeml.com', undefined)).toBe(true);
  });

  it('treats a null/undefined provider as the OAuth (email) path', () => {
    // NextAuth may call signIn with a null account on some adapter paths.
    expect(isSignInAllowed(null, 'alice@example.com', LIST)).toBe(true);
    expect(isSignInAllowed(undefined, 'eve@evil.com', LIST)).toBe(false);
  });
});
