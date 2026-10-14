/**
 * The dashboard sends a first-time user into onboarding (#152), unless they asked
 * to skip it. It fails open: while the status is loading, or could not be read,
 * nobody is redirected.
 */
import { renderHook } from '@testing-library/react';
import { useOnboardingRedirect } from '@/lib/hooks/useOnboardingRedirect';

const status = { isComplete: false, isLoading: false, error: null as string | null };
jest.mock('@/lib/hooks/useOnboardingStatus', () => ({ useOnboardingStatus: () => status }));
jest.mock('@/lib/hooks/useCurrentUser', () => ({ useCurrentUser: () => ({ user: { id: 'u-1' } }) }));

const push = () => (global as unknown as { __NEXT_ROUTER_MOCKS__: { push: jest.Mock } }).__NEXT_ROUTER_MOCKS__.push;

describe('useOnboardingRedirect', () => {
  beforeEach(() => {
    Object.assign(status, { isComplete: false, isLoading: false, error: null });
    window.localStorage.clear();
    window.history.replaceState(null, '', '/dashboard');
  });

  it('sends a user who has not finished onboarding to it', () => {
    renderHook(() => useOnboardingRedirect());
    expect(push()).toHaveBeenCalledWith('/onboarding');
  });

  it.each([
    ['has finished onboarding', { isComplete: true }],
    ['is still being looked up', { isLoading: true }],
    ['could not be looked up', { error: 'offline' }],
  ])('leaves alone a user who %s', (_what, state) => {
    Object.assign(status, state);
    renderHook(() => useOnboardingRedirect());
    expect(push()).not.toHaveBeenCalled();
  });

  it('remembers ?skipOnboarding=true for that user, and only that user', () => {
    window.history.replaceState(null, '', '/dashboard?skipOnboarding=true');
    renderHook(() => useOnboardingRedirect());
    expect(push()).not.toHaveBeenCalled();
    expect(window.localStorage.getItem('onboarding_skipped:u-1')).toBe('true');

    // Back without the parameter: the choice still holds.
    window.history.replaceState(null, '', '/dashboard');
    renderHook(() => useOnboardingRedirect());
    expect(push()).not.toHaveBeenCalled();

    // Another account's flag is not this account's.
    window.localStorage.clear();
    window.localStorage.setItem('onboarding_skipped:someone-else', 'true');
    renderHook(() => useOnboardingRedirect());
    expect(push()).toHaveBeenCalledWith('/onboarding');
  });
});
