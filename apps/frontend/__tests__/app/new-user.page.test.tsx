/**
 * Sign-up page legal notice (issue #473 AC5).
 *
 * This is the page where a person actually forms the contract, so the Terms and
 * Privacy Policy have to be reachable from it before they click through OAuth.
 */

import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { readFileSync } from 'fs';
import { join } from 'path';
import SignUpPage from '@/app/auth/new-user/page';
import { COMPANY } from '@/lib/legal/company';

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

  it('offers both OAuth providers, Google first', () => {
    render(<SignUpPage />);
    const providers = screen.getAllByRole('button').map((button) => button.textContent);
    expect(providers).toEqual([
      expect.stringMatching(/Sign up with Google$/),
      expect.stringMatching(/Sign up with GitHub$/),
    ]);
  });

  // #770 AC4: the page used to be two buttons under "Create an Account", with
  // nothing saying what the account is for.
  it('says what the product does, in the signed value line', () => {
    render(<SignUpPage />);
    expect(screen.getByText(COMPANY.valueLine)).toBeInTheDocument();
  });

  it('the value line is the one the positioning document signed', () => {
    const positioning = readFileSync(
      join(__dirname, '..', '..', '..', '..', 'docs', 'product', 'positioning.md'),
      'utf8',
    );
    expect(positioning).toContain(COMPANY.valueLine);
  });
});
