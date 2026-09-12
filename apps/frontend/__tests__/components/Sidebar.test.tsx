import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import Sidebar from '@/components/Sidebar';

// Mutable so individual tests can flip the server-computed admin flag (#477).
const mockSession: { isAdmin?: boolean; user: { name: string; email: string } } = {
  user: { name: 'Tess', email: 't@example.com' },
};
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: mockSession }),
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
    // Closed: drawer is translated off-canvas AND `invisible` so its links
    // leave the tab order below lg (lg:visible keeps it on desktop).
    const drawer = document.getElementById('app-sidebar')!;
    expect(drawer.classList.contains('-translate-x-full')).toBe(true);
    expect(drawer.classList.contains('invisible')).toBe(true);

    fireEvent.click(toggle);

    const openToggle = screen.getByRole('button', { name: /close navigation menu/i });
    expect(openToggle).toHaveAttribute('aria-expanded', 'true');
    // Open: drawer slides into view (classList tokenizes, so this is the bare
    // `translate-x-0`, not the `lg:translate-x-0` responsive variant).
    expect(drawer.classList.contains('translate-x-0')).toBe(true);
    expect(drawer.classList.contains('-translate-x-full')).toBe(false);
    expect(drawer.classList.contains('visible')).toBe(true);
    expect(drawer.classList.contains('invisible')).toBe(false);
  });

  it('closes the drawer when a nav link is followed', () => {
    render(<Sidebar />);
    fireEvent.click(screen.getByRole('button', { name: /open navigation menu/i }));
    fireEvent.click(screen.getByRole('link', { name: /Load Data/i }));

    const toggle = screen.getByRole('button', { name: /open navigation menu/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('closes the drawer on Escape and returns focus to the hamburger', () => {
    render(<Sidebar />);
    const toggle = screen.getByRole('button', { name: /open navigation menu/i });
    fireEvent.click(toggle);

    fireEvent.keyDown(document.getElementById('app-sidebar')!, { key: 'Escape' });

    const reopened = screen.getByRole('button', { name: /open navigation menu/i });
    expect(reopened).toHaveAttribute('aria-expanded', 'false');
    expect(reopened).toHaveFocus();
  });

  // ---- Admin link is for admins only (issue #477) ----
  //
  // `session.isAdmin` is computed server-side in the NextAuth session callback
  // from ADMIN_EMAILS; the client never sees the allowlist itself. Hiding the
  // link is UX — the route is guarded in middleware regardless.

  it('does not render the Admin link for a non-admin session', () => {
    delete mockSession.isAdmin;
    render(<Sidebar />);
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument();
  });

  it('renders the Admin link only when the session says isAdmin', () => {
    mockSession.isAdmin = true;
    try {
      render(<Sidebar />);
      expect(screen.getByRole('link', { name: /^Admin$/i })).toHaveAttribute('href', '/admin');
    } finally {
      delete mockSession.isAdmin;
    }
  });
});
