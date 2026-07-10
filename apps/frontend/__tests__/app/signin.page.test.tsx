import { render, screen, fireEvent } from '@testing-library/react';
import { signIn } from 'next-auth/react';
import SignInPage from '@/app/auth/signin/page';

// Local mocks override the global jest.setup defaults so we can drive the
// callbackUrl and observe the post-auth redirect.
const push = jest.fn();
let search = new URLSearchParams();
let sessionStatus: 'authenticated' | 'unauthenticated' = 'authenticated';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => search,
}));

jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
  useSession: () => ({ status: sessionStatus }),
}));

const mockSignIn = signIn as jest.MockedFunction<typeof signIn>;

describe('SignInPage open-redirect guard (issue #271)', () => {
  beforeEach(() => {
    push.mockReset();
    mockSignIn.mockReset();
    sessionStatus = 'authenticated';
  });

  it('redirects an off-site callbackUrl to the safe /upload default', () => {
    search = new URLSearchParams({ callbackUrl: 'https://evil.example' });
    render(<SignInPage />);
    expect(push).toHaveBeenCalledWith('/upload');
    expect(push).not.toHaveBeenCalledWith('https://evil.example');
  });

  it('preserves a legitimate relative callbackUrl', () => {
    search = new URLSearchParams({ callbackUrl: '/explore/abc' });
    render(<SignInPage />);
    expect(push).toHaveBeenCalledWith('/explore/abc');
  });

  // All sign-in buttons (Google/GitHub, and the dev-only credentials form) read
  // the same sanitized `callbackUrl` variable, so proving one OAuth path proves
  // them all — the credentials path is identical code, gated to development.
  it('passes the sanitized URL (not the off-site one) to signIn on the OAuth path', () => {
    sessionStatus = 'unauthenticated';
    search = new URLSearchParams({ callbackUrl: 'https://evil.example' });
    render(<SignInPage />);
    fireEvent.click(screen.getByRole('button', { name: /Continue with Google/i }));
    expect(mockSignIn).toHaveBeenCalledWith('google', { callbackUrl: '/upload' });
    expect(mockSignIn).not.toHaveBeenCalledWith(
      'google',
      expect.objectContaining({ callbackUrl: 'https://evil.example' }),
    );
  });
});
