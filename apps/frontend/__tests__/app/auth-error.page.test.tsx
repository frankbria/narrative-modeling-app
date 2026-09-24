/**
 * Auth error page — invite-only "request access" message (issue #261).
 *
 * A rejected sign-in redirects to /auth/error?error=AccessDenied; the page must
 * show a clear invite-only message and a Request access action (not a generic
 * error).
 */

import { render, screen } from '@testing-library/react';
import AuthErrorPage from '@/app/auth/error/page';
import { COMPANY } from '@/lib/legal/company';

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
    // asChild renders the action as a real <a> (role "link"), not a nested <button>.
    expect(screen.getByRole('link', { name: /request access/i })).toBeInTheDocument();
  });

  it('requests access at the company support mailbox by default (#770)', () => {
    mockError = 'AccessDenied';
    render(<AuthErrorPage />);
    expect(screen.getByRole('link', { name: /request access/i }).getAttribute('href')).toBe(
      `mailto:${COMPANY.supportEmail}?subject=Beta%20access%20request`,
    );
  });

  it('shows no Request access action for unrelated errors', () => {
    mockError = 'Configuration';
    render(<AuthErrorPage />);
    expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: /request access/i }),
    ).not.toBeInTheDocument();
  });
});
