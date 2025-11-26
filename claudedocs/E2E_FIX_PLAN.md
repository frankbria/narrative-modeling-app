# E2E Test Fix Plan - Comprehensive Analysis & Execution Strategy

**Generated**: 2025-12-09
**Branch**: `feature/fix-e2e-file-upload-tests`
**Current Pass Rate**: ~17% (4/23 smoke tests)
**Target Pass Rate**: 100% (23/23 smoke tests)

---

## Phase 1: Analysis Summary ✅

### Test Results Snapshot
- **Total Smoke Tests**: 23
- **Exit Code**: 0 (but individual test failures detected)
- **Primary Failures**:
  1. Authentication fixture issues (SKIP_AUTH not working properly)
  2. Upload → Explore navigation failures
  3. Test timeouts waiting for authentication elements that shouldn't exist

### Critical Findings

#### 1. Authentication Fixture Failure (HIGH PRIORITY)
**Location**: `apps/frontend/e2e/fixtures/index.ts:90-112`

**Problem**: The `authenticatedPage` fixture is looking for password input fields even when `SKIP_AUTH=true` is set:
```typescript
// Line 102: Error shows it's trying to fill password field
locator('input[name="password"], input[type="password"]').first()
```

**Impact**: Causes test timeouts in:
- `predict.spec.ts` tests (2 failures)
- Any test using `authenticatedPage` fixture with SKIP_AUTH

**Root Cause**: Fixture logic doesn't properly detect SKIP_AUTH mode before attempting authentication flow.

#### 2. Upload Navigation Issue (HIGH PRIORITY)
**Location**: `apps/frontend/app/upload/page.tsx`

**Problem**: Multiple navigation triggers exist but E2E tests expect immediate navigation to `/explore/[id]`:
- Line 124: After chunked upload
- Line 137: useEffect with uploadedFileId dependency
- Line 260: After regular upload
- Line 329: After PII confirmation

**Issue**: Navigation might be blocked or delayed in E2E test environment.

**Test Expectation**: `UploadPage.ts:85` - `waitForUploadComplete()` expects URL pattern `/explore/[a-zA-Z0-9-]+/`

#### 3. Configuration Warnings (MEDIUM PRIORITY)
**Issues**:
- Next.js config using deprecated `experimental.serverComponentsExternalPackages`
- Workspace root detection warning (multiple package-lock.json files)

---

## Phase 2: Parallel Root Cause Investigation 🔍

### Subagent Execution Plan

#### Agent 1: Authentication Fixture Debugger
**Focus**: Fix authenticatedPage fixture to properly handle SKIP_AUTH
- Analyze fixture authentication logic
- Identify where password field lookup occurs
- Implement proper SKIP_AUTH detection
- Add conditional authentication flow

#### Agent 2: Upload Navigation Investigator
**Focus**: Debug upload → explore navigation failures
- Trace router.push() calls in upload page
- Check Next.js App Router navigation in test environment
- Identify navigation blocking issues
- Test useEffect dependency triggering

#### Agent 3: Test Infrastructure Reviewer
**Focus**: Configuration and test environment issues
- Review Next.js config deprecations
- Check environment variable propagation (SKIP_AUTH, NEXT_PUBLIC_SKIP_AUTH)
- Validate playwright.config.ts settings
- Review middleware auth bypass logic

---

## Phase 3: Fix Implementation Strategy

### Priority 1: Authentication Fixture (P0)
**Files to Modify**:
- `apps/frontend/e2e/fixtures/index.ts` (authenticatedPage fixture)

**Proposed Fix**:
```typescript
// Check if SKIP_AUTH is enabled before attempting authentication
const skipAuth = process.env.SKIP_AUTH === 'true' ||
                 process.env.NEXT_PUBLIC_SKIP_AUTH === 'true';

if (skipAuth) {
  // Just navigate to dashboard, no auth needed
  await page.goto('/dashboard', { timeout: 30000 });
  await page.waitForLoadState('networkidle', { timeout: 10000 });
} else {
  // Perform authentication flow
  // ... existing auth logic
}
```

### Priority 2: Upload Navigation (P0)
**Files to Modify**:
- `apps/frontend/app/upload/page.tsx` (consolidate navigation logic)
- `apps/frontend/e2e/pages/UploadPage.ts` (improve wait strategies)

**Proposed Fix**:
```typescript
// Option A: Add explicit navigation trigger after upload success
await page.waitForResponse(resp => resp.url().includes('/upload/secure') && resp.status() === 200);
await page.waitForURL(/\/explore\/[a-zA-Z0-9-]+/, { timeout: 30000 });

// Option B: Use element-based wait instead of URL wait
await uploadPage.page.waitForSelector('[data-testid="explore-page-loaded"]', { timeout: 30000 });
```

### Priority 3: Configuration Cleanup (P1)
**Files to Modify**:
- `apps/frontend/next.config.mjs`
- Root `package-lock.json` (consider removing if not needed)

---

## Phase 4: Validation & Testing

### Test Execution Sequence
1. **Unit Fix Validation**: Test each fix in isolation
2. **Smoke Test Run**: `npm run test:e2e:smoke`
3. **Full Suite Run**: `npm run test:e2e:full`
4. **Cross-Browser Validation**: Firefox & WebKit tests

### Success Criteria
- ✅ All 23 smoke tests pass (100% pass rate)
- ✅ No authentication timeouts
- ✅ Upload → Explore navigation works reliably
- ✅ No configuration warnings in test output
- ✅ Tests complete in < 5 minutes

---

## Subagent Launch Commands

### Execute Parallel Investigation (Phase 2)
```bash
# Launch 3 parallel agents for root cause analysis
claude-agent-1: Analyze authentication fixture
claude-agent-2: Debug upload navigation
claude-agent-3: Review test infrastructure
```

### Post-Fix Validation (Phase 4)
```bash
# Run smoke tests after fixes
npm run test:e2e:smoke

# Run full suite
npm run test:e2e:full

# Generate report
npx playwright show-report
```

---

## Risk Assessment

### High Risk Areas
1. **Authentication Bypass**: Must ensure SKIP_AUTH doesn't leak to production
2. **Navigation Timing**: Race conditions between upload completion and navigation
3. **Environment Variables**: Proper propagation in CI/CD pipelines

### Mitigation Strategies
1. Add explicit SKIP_AUTH checks with clear logging
2. Use Playwright's built-in wait strategies (waitForURL, waitForResponse)
3. Add environment variable validation in playwright.config.ts

---

## Next Steps

1. ✅ **Phase 1 Complete**: Analysis and problem identification
2. 🔄 **Phase 2 Starting**: Launch 3 parallel subagents for root cause investigation
3. ⏳ **Phase 3 Pending**: Implement fixes based on agent findings
4. ⏳ **Phase 4 Pending**: Validate fixes and achieve 100% pass rate

---

## References

- Session Log: `claudedocs/SESSION.md`
- Previous Session: `claudedocs/2025-12-03_SESSION.md`
- GitHub Actions: E2E Full Suite workflow
- Test Files: `apps/frontend/e2e/workflows/*.spec.ts`
