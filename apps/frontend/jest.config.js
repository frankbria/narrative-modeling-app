const nextJest = require('next/jest')

const createJestConfig = nextJest({
  // Provide the path to your Next.js app to load next.config.js and .env files
  dir: './',
})

// Add any custom config to be passed to Jest
const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  transformIgnorePatterns: [
    'node_modules/(?!(react-markdown|remark-*|unist-*|unified|bail|is-plain-obj|trough|vfile|micromark|mdast-*|escape-string-regexp|zwitch)/)',
  ],
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/.next/',
    '<rootDir>/e2e/',  // Exclude Playwright E2E tests from Jest
    '<rootDir>/__tests__/utils/',  // Exclude test utility helpers from test runs
  ],
  collectCoverageFrom: [
    'components/**/*.{ts,tsx}',
    'app/**/*.{ts,tsx}',
    'lib/**/*.{ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
  ],
}

// next/jest prepends its own `node_modules/(?!.pnpm)(?!(geist|next/...)/)`
// ignore pattern, and jest skips transforming a file that matches ANY pattern —
// so a package we add to our own entry above is still ignored by next's. Some
// deps are ESM-only and MUST be transformed to load under jest, notably
// @auth/core|jose|@panva/hkdf, needed to exercise the real next-auth `getToken`
// cookie resolution (#469) instead of mocking it blind. Inject those into
// next/jest's own negative lookahead after it resolves.
const ESM_TO_TRANSFORM = 'next-auth|@auth/core|jose|@panva/hkdf'
module.exports = async () => {
  const config = await createJestConfig(customJestConfig)()
  // A file is ignored (not transformed) if it matches ANY pattern, so the ESM
  // packages must be allowed through EVERY node_modules negative-lookahead, both
  // next/jest's (anchored on `geist`) and ours (anchored on `react-markdown`).
  config.transformIgnorePatterns = config.transformIgnorePatterns.map((pattern) =>
    pattern
      .replace('(?!(geist|', `(?!(${ESM_TO_TRANSFORM}|geist|`)
      .replace('(?!(react-markdown|', `(?!(${ESM_TO_TRANSFORM}|react-markdown|`),
  )
  return config
}
