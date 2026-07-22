import '@testing-library/jest-dom'
import { toHaveNoViolations } from 'jest-axe'

// jest-axe custom matcher for accessibility smoke tests (issue #282).
expect.extend(toHaveNoViolations)

// DOM polyfills only apply under the jsdom environment. Node-environment tests
// (e.g. API route handlers via `@jest-environment node`) have no `Element`/`window`.
if (typeof Element !== 'undefined') {
  // Polyfill for Radix UI pointer capture in JSDOM
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = function() {
      return false;
    };
  }

  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = function() {};
  }

  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = function() {};
  }

  // Polyfill for scrollIntoView in JSDOM
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function() {};
  }
}

// Mock ResizeObserver for Radix UI components
global.ResizeObserver = class ResizeObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Stable, assertable router spies. Previously useRouter() returned a fresh
// jest.fn() on every call, so a test could never assert router.push(...) via
// the global mock. These module-level spies persist across renders and are
// cleared before each test; a test that doesn't re-mock next/navigation can
// assert redirects via global.__NEXT_ROUTER_MOCKS__.push.
const routerMocks = {
  push: jest.fn(),
  replace: jest.fn(),
  prefetch: jest.fn(),
  back: jest.fn(),
}
global.__NEXT_ROUTER_MOCKS__ = routerMocks

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => routerMocks,
  useParams: () => ({
    id: 'test-dataset-id'
  }),
  useSearchParams: () => new URLSearchParams(),
}))

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: {
      user: {
        id: 'mock-user-id',
        email: 'test@example.com',
        name: 'Test User'
      },
      expires: '2024-12-31T23:59:59.999Z'
    },
    status: 'authenticated'
  }),
  SessionProvider: ({ children }) => children,
}))

// Mock auth helpers
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token')
}))

// Mock react-markdown
jest.mock('react-markdown', () => {
  return function ReactMarkdown({ children }) {
    return children
  }
})

// Mock fetch
global.fetch = jest.fn()

// Mock window.open (jsdom only)
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'open', {
    writable: true,
    value: jest.fn(),
  })
}

// Reset shared spies before each test.
beforeEach(() => {
  routerMocks.push.mockClear()
  routerMocks.replace.mockClear()
  routerMocks.prefetch.mockClear()
  routerMocks.back.mockClear()

  // Default fetch REJECTS. Previously it resolved to `{ ok: true, json: () => ({}) }`,
  // which silently returned empty success for any unmocked request — hiding
  // contract/redirect regressions (a component fetching real data got `{}` and
  // still "passed"). Tests that hit the network must stub fetch explicitly.
  fetch.mockReset()
  global.fetch.mockRejectedValue(
    new Error('Unmocked fetch call — stub global.fetch explicitly in this test')
  )
})