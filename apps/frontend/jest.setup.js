import '@testing-library/jest-dom'

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

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
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

// Setup mock responses
beforeEach(() => {
  fetch.mockClear()
  global.fetch.mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue({}),
  })
})