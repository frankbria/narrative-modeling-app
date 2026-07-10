import { render } from '@testing-library/react';
import SignInPage from '@/app/auth/signin/page';

// Local mocks override the global jest.setup defaults so we can drive the
// callbackUrl and observe the post-auth redirect.
const push = jest.fn();
let search = new URLSearchParams();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => search,
}));

jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
  useSession: () => ({ status: 'authenticated' }),
}));

describe('SignInPage open-redirect guard (issue #271)', () => {
  beforeEach(() => push.mockReset());

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
});
