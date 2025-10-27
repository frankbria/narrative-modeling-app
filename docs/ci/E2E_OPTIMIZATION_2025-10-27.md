# E2E CI Optimization Summary (2025-10-27)

## Problem
E2E tests were timing out at 20-30 minutes without completing test execution.

## Root Cause Discovery
Used timestamp analysis to identify that jobs were timing out during browser installation, not test execution:
- **Install Playwright Browsers**: 1187 seconds (19.8 minutes)
- **Run E2E Full Suite**: 0 seconds (never started)

Each job was installing ALL 3 browsers (chromium, firefox, webkit) even though each job only needed one browser.

## Optimizations Implemented

### 1. Browser Installation Optimization
**Changed**: Only install the browser required for each job
**Implementation**: Extract browser name from matrix.project and install with `npx playwright install --with-deps $BROWSER`
**Result**: 70 seconds vs 1187 seconds (94% reduction)

### 2. Test Sharding
**Changed**: Split test suite into 3 shards per browser
**Implementation**: Matrix strategy with `shard: [1/3, 2/3, 3/3]`
**Result**: ~70 tests per shard vs 210 tests, better parallelization

### 3. Worker Configuration
**Maintained**: 4 workers per job for parallel test execution
**Note**: GitHub Actions runners have 2 cores, 4 workers is optimal

### 4. Artifact Name Fix
**Changed**: Convert shard notation from `1/3` to `1-3` for artifact names
**Implementation**: Bash step using `tr '/' '-'` command
**Reason**: GitHub Actions artifact names cannot contain slashes

## Performance Results

### Before Optimization
- Browser installation: 1187 seconds (19.8 min)
- Test execution: 0 seconds (timed out)
- **Total**: Timeout at 20+ minutes ❌

### After Optimization
- Browser installation: 70 seconds (1.2 min)
- Test execution: 731 seconds (12.2 min)
- **Total**: 830 seconds (13.8 min) ✅
- **Buffer**: 6+ minutes before 20-minute timeout

## Files Modified
- `.github/workflows/e2e-tests.yml` - Browser installation, sharding, artifact names
- `apps/frontend/playwright.config.ts` - Worker configuration (already at 4)

## Current Status
- **Infrastructure**: ✅ Fixed - Tests complete within timeout
- **Test Failures**: 7 E2E tests failing (tracked in Issue #35)
- **Next Steps**: Investigate and fix failing E2E tests

## Key Learnings
1. **Use timestamp analysis** to identify bottlenecks, not guesswork
2. **Browser installation time** can be a major CI bottleneck
3. **Install only what's needed** - don't install all browsers for every job
4. **Sharding** improves parallelization and prevents timeout issues
5. **Artifact naming** must be filesystem-safe (no slashes)

## Run History
- Run 18850792673: 2-way sharding, all browsers installed (timed out at 20 min)
- Run 18849791975: 4 workers (timed out at 30 min)
- Run 18851461258: Browser optimization, syntax error in workflow
- Run 18852406822: All optimizations applied ✅ (completed in 13.8 min)
