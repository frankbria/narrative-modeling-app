import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import Sidebar from '@/components/Sidebar';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { name: 'Tess', email: 't@example.com' } } }),
  signOut: jest.fn(),
}));

describe('Sidebar navigation', () => {
  it('links to the training jobs dashboard after Build Model', () => {
    render(<Sidebar />);

    const trainingLink = screen.getByRole('link', { name: /Training Jobs/i });
    expect(trainingLink).toHaveAttribute('href', '/training');

    // Placed directly after Build Model in the workflow nav.
    const links = screen
      .getAllByRole('link')
      .map((link) => link.textContent?.trim());
    const buildModelIndex = links.indexOf('Build Model');
    expect(buildModelIndex).toBeGreaterThanOrEqual(0);
    expect(links[buildModelIndex + 1]).toBe('Training Jobs');
  });
});
