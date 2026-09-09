/**
 * Sign-up page legal notice (issue #473 AC5).
 *
 * This is the page where a person actually forms the contract, so the Terms and
 * Privacy Policy have to be reachable from it before they click through OAuth.
 */

import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import SignUpPage from '@/app/auth/new-user/page';

jest.mock('next-auth/react', () => ({ signIn: jest.fn() }));

describe('SignUpPage', () => {
  it('links the Terms and Privacy Policy from the sign-up flow', () => {
    render(<SignUpPage />);
    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute(
      'href',
      '/legal/terms',
    );
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute(
      'href',
      '/legal/privacy',
    );
  });

  it('still offers both OAuth providers', () => {
    render(<SignUpPage />);
    expect(screen.getByRole('button', { name: /sign up with google/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign up with github/i })).toBeInTheDocument();
  });
});
