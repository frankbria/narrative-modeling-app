# E2E Authentication Migration - SKIP_AUTH Removal

## Overview

This document describes the migration from the insecure `SKIP_AUTH` environment variable to a proper test user authentication mechanism for E2E testing.

## Security Issue

The previous implementation used a `SKIP_AUTH` environment variable that completely bypassed authentication when set to `true`. This approach had several security concerns:

1. **Accidental Production Deployment**: Could be accidentally enabled in production
2. **No Real Authentication Testing**: Tests didn't verify actual authentication flows
3. **Security Risk**: Complete auth bypass is a dangerous pattern

## New Implementation

### Test User with Credentials Provider

Instead of bypassing authentication, we now use a proper test user with NextAuth Credentials provider:

**Test Credentials:**
- Email: `test@narrativeml.com`
- Password: `test-password-123`
- User ID: `test-user-12345`

### Global Setup Authentication

Playwright now uses a global setup script that:
1. Authenticates once before all tests
2. Saves the session state to `.auth/user.json`
3. All tests reuse this authenticated session

**File: `apps/frontend/e2e/global-setup.ts`**

This approach is:
- More secure (uses real authentication)
- More efficient (authenticate once, not for every test)
- More realistic (tests actual auth flows)

### Storage State

The authenticated session is stored in Playwright's storage state format and automatically loaded for all tests via `playwright.config.ts`:

```typescript
use: {
  storageState: './e2e/.auth/user.json',
}
```

## Changes Made

### Frontend Code Changes

1. **auth.ts** - Added Credentials provider for test users (only in development/test mode)
2. **middleware.ts** - Removed SKIP_AUTH check, now enforces auth for all protected routes
3. **app/layout.tsx** - Removed SKIP_AUTH mock session logic
4. **app/auth/signin/page.tsx** - Updated to show test user login form instead of SKIP_AUTH bypass
5. **lib/db.ts** - Replaced SKIP_AUTH with CI-only check
6. **lib/auth-helpers.ts** - Removed SKIP_AUTH logic

### E2E Test Infrastructure Changes

1. **playwright.config.ts**:
   - Added `globalSetup` pointing to `e2e/global-setup.ts`
   - Added `storageState` configuration
   - Removed `SKIP_AUTH` environment variables from webServer

2. **e2e/global-setup.ts** - New file that authenticates and saves session state

3. **e2e/fixtures/auth.ts** - Simplified to use storage state instead of SKIP_AUTH

4. **e2e/fixtures/index.ts** - Removed complex SKIP_AUTH logic, now uses storage state

5. **test-e2e.sh** - Removed SKIP_AUTH environment variables

### CI/CD Changes

1. **.github/workflows/e2e-tests.yml** - Updated env vars to use TEST_USER_* instead of SKIP_AUTH
2. **.github/workflows/smoke-tests.yml** - Updated env vars to use TEST_USER_* instead of SKIP_AUTH

## Environment Variables

### Old (Removed)
```bash
SKIP_AUTH=true
NEXT_PUBLIC_SKIP_AUTH=true
```

### New (Required for E2E)
```bash
NODE_ENV=development
TEST_USER_EMAIL=test@narrativeml.com  # Optional, has default
TEST_USER_PASSWORD=test-password-123  # Optional, has default
```

## Running E2E Tests

### Local Development

```bash
cd apps/frontend
./test-e2e.sh
```

The test script will:
1. Start the backend server
2. Start the frontend dev server
3. Run Playwright global setup (authenticate once)
4. Run all E2E tests with the saved session

### CI/CD

GitHub Actions workflows automatically:
1. Set TEST_USER_* environment variables
2. Run Playwright with proper authentication
3. Reuse the authenticated session across all tests

## Benefits

1. **Security**: No authentication bypass in production code
2. **Realism**: Tests actual authentication flows
3. **Efficiency**: Authenticate once, not per test
4. **Maintainability**: Standard Playwright patterns
5. **Type Safety**: Proper TypeScript types for test users

## Backend Note

The backend still has `SKIP_AUTH` for its own testing purposes. This is acceptable because:
- Backend tests are isolated and don't affect frontend security
- Backend SKIP_AUTH is only used in test environments
- Frontend E2E tests no longer depend on it

## Migration Checklist

- [x] Add Credentials provider to auth.ts
- [x] Create global-setup.ts for authentication
- [x] Update playwright.config.ts with globalSetup and storageState
- [x] Remove SKIP_AUTH from middleware.ts
- [x] Remove SKIP_AUTH from layout.tsx
- [x] Update signin page to show test user form
- [x] Simplify E2E fixtures to use storage state
- [x] Update test-e2e.sh script
- [x] Update GitHub Actions workflows
- [x] Remove SKIP_AUTH references from lib files
- [x] Document changes

## Testing

After migration, verify:

1. **Local E2E Tests**: Run `./test-e2e.sh` - should pass
2. **Authentication Flow**: Global setup should authenticate successfully
3. **Session Persistence**: All tests should use the saved session
4. **No SKIP_AUTH**: Grep codebase to ensure SKIP_AUTH is removed from frontend

## Troubleshooting

### Tests Fail with "redirected to signin page"
- Check that global-setup.ts is configured in playwright.config.ts
- Verify storageState file exists at `e2e/.auth/user.json`
- Ensure TEST_USER_* env vars are set correctly

### Global setup fails to authenticate
- Check that NODE_ENV=development (enables Credentials provider)
- Verify test credentials match those in auth.ts
- Check that the dev server is running before global setup

### Session not persisting
- Ensure storageState path is correct in playwright.config.ts
- Check that .auth directory is not in .gitignore
- Verify the session cookie is being saved correctly

## References

- [Playwright Authentication Guide](https://playwright.dev/docs/auth)
- [NextAuth Credentials Provider](https://next-auth.js.org/providers/credentials)
- [Playwright Global Setup](https://playwright.dev/docs/test-global-setup-teardown)
