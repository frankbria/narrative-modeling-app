import '@testing-library/jest-dom'

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

// Mock @clerk/nextjs
jest.mock('@clerk/nextjs', () => ({
  useAuth: () => ({
    getToken: jest.fn().mockResolvedValue('mock-token'),
    isSignedIn: true,
    userId: 'mock-user-id',
  }),
  ClerkProvider: ({ children }) => children,
}))

// Mock react-markdown
jest.mock('react-markdown', () => {
  return function ReactMarkdown({ children }) {
    return children
  }
})

// Mock fetch
global.fetch = jest.fn()

// Mock window.open
Object.defineProperty(window, 'open', {
  writable: true,
  value: jest.fn(),
})

// Setup mock responses
beforeEach(() => {
  fetch.mockClear()
  global.fetch.mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue({}),
  })
})