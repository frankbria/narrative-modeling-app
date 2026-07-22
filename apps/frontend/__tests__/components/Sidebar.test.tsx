import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

  // ---- Responsive drawer + labeled nav (issue #282) ----

  it('exposes the nav as a labeled region', () => {
    render(<Sidebar />);
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument();
  });

  it('toggles the off-canvas drawer via the hamburger button', () => {
    render(<Sidebar />);
    const toggle = screen.getByRole('button', { name: /open navigation menu/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveAttribute('aria-controls', 'app-sidebar');
    // Closed: drawer is translated off-canvas.
    const drawer = document.getElementById('app-sidebar')!;
    expect(drawer.classList.contains('-translate-x-full')).toBe(true);

    fireEvent.click(toggle);

    const openToggle = screen.getByRole('button', { name: /close navigation menu/i });
    expect(openToggle).toHaveAttribute('aria-expanded', 'true');
    // Open: drawer slides into view (classList tokenizes, so this is the bare
    // `translate-x-0`, not the `lg:translate-x-0` responsive variant).
    expect(drawer.classList.contains('translate-x-0')).toBe(true);
    expect(drawer.classList.contains('-translate-x-full')).toBe(false);
  });

  it('closes the drawer when a nav link is followed', () => {
    render(<Sidebar />);
    fireEvent.click(screen.getByRole('button', { name: /open navigation menu/i }));
    fireEvent.click(screen.getByRole('link', { name: /Load Data/i }));

    const toggle = screen.getByRole('button', { name: /open navigation menu/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });
});
