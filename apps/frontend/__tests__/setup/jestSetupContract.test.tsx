/**
 * Locks in the global jest.setup test-harness contract (issue #268):
 *   1. Unmocked `fetch` REJECTS (so silent-`{}` regressions surface).
 *   2. `next/navigation` router spies are stable and assertable across renders,
 *      and cleared before each test — exposed as global.__NEXT_ROUTER_MOCKS__.
 *
 *   3. The page's public settings are the test's process environment (#831): no
 *      server renders a jest page, and a suite that sets
 *      `process.env.NEXT_PUBLIC_API_URL` means "this deployment's API".
 *
 * If someone reverts the harden-mocks change, these tests fail loudly.
 */

import React from 'react';
import { render } from '@testing-library/react';
import { useRouter } from 'next/navigation';
import { publicEnv } from '@/lib/runtimeEnv';

describe('jest.setup contract', () => {
  it('reads a public setting from the process environment the test set', () => {
    const original = process.env.NEXT_PUBLIC_API_URL;
    try {
      process.env.NEXT_PUBLIC_API_URL = 'https://set-by-a-test.example/api/v1';
      expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://set-by-a-test.example/api/v1');
    } finally {
      process.env.NEXT_PUBLIC_API_URL = original;
    }
  });

  it('rejects unmocked fetch calls by default', async () => {
    await expect(fetch('/api/anything')).rejects.toThrow(/Unmocked fetch/);
  });

  it('exposes a stable router push spy via global.__NEXT_ROUTER_MOCKS__', () => {
    const spy = (global as any).__NEXT_ROUTER_MOCKS__;
    expect(spy).toBeDefined();

    function Nav() {
      const router = useRouter();
      // useRouter() must return the SAME stable object the global exposes.
      expect(router.push).toBe(spy.push);
      React.useEffect(() => {
        router.push('/destination');
      }, [router]);
      return null;
    }

    render(<Nav />);
    expect(spy.push).toHaveBeenCalledWith('/destination');
  });

  it('clears the router push spy between tests', () => {
    // The previous test called push once; beforeEach must have reset it.
    expect((global as any).__NEXT_ROUTER_MOCKS__.push).not.toHaveBeenCalled();
  });
});
