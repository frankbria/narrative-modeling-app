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