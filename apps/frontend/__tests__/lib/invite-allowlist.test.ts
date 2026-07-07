/**
 * Invite-only beta gate — allowlist logic (issue #261).
 *
 * Asserts the AC directly: a non-allowlisted email is denied and an
 * allowlisted one is admitted, plus the gate-disabled (empty list) default.
 */

import { parseAllowlist, isEmailAllowed } from '@/lib/invite-allowlist';

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

  it('reads process.env.INVITE_ALLOWLIST by default', () => {
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
