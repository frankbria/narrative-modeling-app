/**
 * @jest-environment node
 *
 * mintApiToken must produce a standard HS256 JWT that the FastAPI backend
 * (jose.jwt.decode with NEXTAUTH_SECRET, reading `sub`) accepts. We verify the
 * signature independently with node:crypto (the backend re-does the same HMAC
 * check), proving the token is genuinely signed, not just well-shaped.
 */
import { createHmac } from 'node:crypto';
import { mintApiToken } from '@/lib/api-token';

const SECRET = 'test-secret-for-api-token';

function verify(token: string, secret: string): Record<string, unknown> {
  const [header, payload, sig] = token.split('.');
  const expected = createHmac('sha256', secret).update(`${header}.${payload}`).digest('base64url');
  if (sig !== expected) {
    throw new Error('signature mismatch');
  }
  return JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
}

describe('mintApiToken', () => {
  const orig = process.env.NEXTAUTH_SECRET;
  beforeEach(() => {
    process.env.NEXTAUTH_SECRET = SECRET;
  });
  // Restore after every test so the delete-secret case can't leak into a later
  // test if Jest reorders execution.
  afterEach(() => {
    process.env.NEXTAUTH_SECRET = SECRET;
  });
  afterAll(() => {
    process.env.NEXTAUTH_SECRET = orig;
  });

  it('produces a 3-part HS256 JWT with the userId as sub and a future expiry', () => {
    const token = mintApiToken('user_123');

    expect(token.split('.')).toHaveLength(3);
    const header = JSON.parse(Buffer.from(token.split('.')[0], 'base64url').toString('utf8'));
    expect(header).toEqual({ alg: 'HS256', typ: 'JWT' });

    const claims = verify(token, SECRET);
    expect(claims.sub).toBe('user_123');
    expect(claims.exp as number).toBeGreaterThan(Math.floor(Date.now() / 1000));
  });

  it('fails verification with the wrong secret (the signature is real)', () => {
    const token = mintApiToken('user_123');
    expect(() => verify(token, 'wrong-secret')).toThrow('signature mismatch');
  });

  it('throws when NEXTAUTH_SECRET is not set', () => {
    delete process.env.NEXTAUTH_SECRET;
    expect(() => mintApiToken('user_123')).toThrow(/NEXTAUTH_SECRET/);
  });
});
