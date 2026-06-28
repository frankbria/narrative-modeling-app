import { getSession } from 'next-auth/react';

// jest.setup.js globally mocks @/lib/auth-helpers; test the real implementation.
jest.unmock('@/lib/auth-helpers');
const { getAuthToken } = jest.requireActual('@/lib/auth-helpers');

jest.mock('next-auth/react', () => ({ getSession: jest.fn() }));

const mockGetSession = getSession as jest.MockedFunction<typeof getSession>;

describe('getAuthToken', () => {
  beforeEach(() => mockGetSession.mockReset());

  it('returns the session apiToken (the real signed JWT, not a placeholder)', async () => {
    const realToken = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEifQ.sig';
    mockGetSession.mockResolvedValue({
      user: { id: 'user_1' },
      apiToken: realToken,
      expires: '2099-01-01',
    } as never);

    await expect(getAuthToken()).resolves.toBe(realToken);
  });

  it('never returns the legacy nextauth-<id> placeholder', async () => {
    mockGetSession.mockResolvedValue({
      user: { id: 'user_1' },
      apiToken: 'header.payload.sig',
      expires: '2099-01-01',
    } as never);

    const token = await getAuthToken();
    expect(token).not.toMatch(/^nextauth-/);
  });

  it('returns null when there is no session', async () => {
    mockGetSession.mockResolvedValue(null);
    await expect(getAuthToken()).resolves.toBeNull();
  });

  it('returns null when the session has no apiToken', async () => {
    mockGetSession.mockResolvedValue({
      user: { id: 'user_1' },
      expires: '2099-01-01',
    } as never);
    await expect(getAuthToken()).resolves.toBeNull();
  });
});
