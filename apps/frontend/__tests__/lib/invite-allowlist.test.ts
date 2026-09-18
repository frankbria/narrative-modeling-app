/**
 * Signup gate — SIGNUP_MODE + invite allowlist (issues #261, #768).
 *
 * Mirrors apps/backend/tests/test_security/test_invite_allowlist.py: an explicit
 * mode wins, unset fails CLOSED in production, dev keeps the legacy default.
 */

import { parseAllowlist, resolveSignupMode, isSignInAllowed } from '@/lib/invite-allowlist';

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

describe('resolveSignupMode', () => {
  const none = new Set<string>();

  it('an explicit value wins in every environment', () => {
    for (const prod of [true, false]) {
      expect(resolveSignupMode('open', none, prod)).toBe('open');
      expect(resolveSignupMode(' Invite ', none, prod)).toBe('invite');
    }
  });

  it('unset in production is invite (fails closed)', () => {
    expect(resolveSignupMode(undefined, none, true)).toBe('invite');
    expect(resolveSignupMode('  ', none, true)).toBe('invite');
  });

  it('unset in dev keeps the legacy behaviour', () => {
    expect(resolveSignupMode(undefined, none, false)).toBe('open');
    expect(resolveSignupMode(undefined, new Set(['a@x.com']), false)).toBe('invite');
  });

  it('an unknown value fails closed', () => {
    expect(resolveSignupMode('opne', none, false)).toBe('invite');
  });
});

describe('isSignInAllowed', () => {
  const invite = { SIGNUP_MODE: 'invite', INVITE_ALLOWLIST: 'alice@example.com', NODE_ENV: 'production' };

  it('invite mode checks OAuth sign-ins against the allowlist by email', () => {
    expect(isSignInAllowed('google', 'alice@example.com', invite)).toBe(true);
    expect(isSignInAllowed('google', 'ALICE@example.com', invite)).toBe(true);
    expect(isSignInAllowed('github', 'eve@evil.com', invite)).toBe(false);
    expect(isSignInAllowed('github', null, invite)).toBe(false);
  });

  it('invite mode with an empty allowlist admits nobody', () => {
    expect(isSignInAllowed('google', 'alice@example.com', { ...invite, INVITE_ALLOWLIST: '' })).toBe(false);
  });

  it('production with nothing set admits nobody', () => {
    expect(isSignInAllowed('google', 'eve@evil.com', { NODE_ENV: 'production' })).toBe(false);
  });

  it('open mode admits any OAuth account', () => {
    expect(isSignInAllowed('google', 'eve@evil.com', { SIGNUP_MODE: 'open', NODE_ENV: 'production' })).toBe(true);
  });

  it('rejects the credentials provider in invite mode, even with an allowlisted email', () => {
    // The credentials provider self-attests its email, so it must never
    // satisfy the email gate.
    expect(isSignInAllowed('credentials', 'alice@example.com', invite)).toBe(false);
  });

  it('allows the credentials provider in dev/test with nothing set', () => {
    expect(isSignInAllowed('credentials', 'test@narrativeml.com', { NODE_ENV: 'test' })).toBe(true);
    expect(isSignInAllowed('credentials', 'test@narrativeml.com', { NODE_ENV: 'development' })).toBe(true);
  });

  it('treats a null/undefined provider as the OAuth (email) path', () => {
    expect(isSignInAllowed(null, 'alice@example.com', invite)).toBe(true);
    expect(isSignInAllowed(undefined, 'eve@evil.com', invite)).toBe(false);
  });

  it('reads process.env by default', () => {
    const prev = { ...process.env };
    process.env.SIGNUP_MODE = 'invite';
    process.env.INVITE_ALLOWLIST = 'alice@example.com';
    try {
      expect(isSignInAllowed('google', 'alice@example.com')).toBe(true);
      expect(isSignInAllowed('google', 'eve@evil.com')).toBe(false);
    } finally {
      process.env = prev;
    }
  });
});
