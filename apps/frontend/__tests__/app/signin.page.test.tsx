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

describe('SignInPage legal notice (issue #473 AC5)', () => {
  beforeEach(() => {
    push.mockReset();
    mockSignIn.mockReset();
    sessionStatus = 'unauthenticated';
    search = new URLSearchParams();
  });

  it('links the Terms and Privacy Policy from the sign-in flow', () => {
    render(<SignInPage />);
    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute(
      'href',
      '/legal/terms',
    );
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute(
      'href',
      '/legal/privacy',
    );
  });
});

// Auth.js sends a failed sign-in back to this page as `?error=<type>`. The page
// used to ignore it, so a refused sign-in looked like nothing had happened.
describe('SignInPage sign-in errors', () => {
  beforeEach(() => {
    sessionStatus = 'unauthenticated';
  });

  it('explains an email that is registered with another provider', () => {
    search = new URLSearchParams({ error: 'OAuthAccountNotLinked' });
    render(<SignInPage />);
    expect(screen.getByRole('alert')).toHaveTextContent(/different sign-in method/i);
  });

  it('shows a generic message for any other error, never the raw parameter', () => {
    search = new URLSearchParams({ error: '<b>SomethingElse</b>' });
    render(<SignInPage />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(/sign-in failed/i);
    expect(alert).not.toHaveTextContent('SomethingElse');
  });

  // A plain-object lookup resolves these to Object.prototype members, which
  // React cannot render: `?error=__proto__` used to crash the page.
  it.each(['__proto__', 'toString', 'constructor'])(
    'treats the inherited key %s as an unknown error',
    (key) => {
      search = new URLSearchParams({ error: key });
      render(<SignInPage />);
      expect(screen.getByRole('alert')).toHaveTextContent(/sign-in failed/i);
    },
  );

  it('shows nothing when there is no error', () => {
    search = new URLSearchParams();
    render(<SignInPage />);
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
