/**
 * Auth error page — invite-only "request access" message (issue #261).
 *
 * A rejected sign-in redirects to /auth/error?error=AccessDenied; the page must
 * show a clear invite-only message and a Request access action (not a generic
 * error).
 */

import { render, screen } from '@testing-library/react';
import AuthErrorPage from '@/app/auth/error/page';

let mockError: string | null = 'AccessDenied';

jest.mock('next/navigation', () => ({
  useSearchParams: () => ({ get: () => mockError }),
}));

describe('AuthErrorPage', () => {
  it('shows an invite-only message and Request access button for AccessDenied', () => {
    mockError = 'AccessDenied';
    render(<AuthErrorPage />);
    expect(screen.getByText('Invite Required')).toBeInTheDocument();
    expect(screen.getByText(/invite-only beta/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request access/i })).toBeInTheDocument();
  });

  it('shows no Request access button for unrelated errors', () => {
    mockError = 'Configuration';
    render(<AuthErrorPage />);
    expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /request access/i }),
    ).not.toBeInTheDocument();
  });
});
