# Story 12.5: End-to-End Integration Testing

**Status**: 🟡 **PLANNED**

**Priority**: 🔴 **CRITICAL** (Production readiness validation)

**Story Points**: 8

**Sprint**: Sprint 12

---

## User Story

**As a** QA engineer and developer
**I want** comprehensive E2E tests for new model architecture
**So that** we can validate complete user workflows with live AI recommendations before production deployment

---

## Context

Sprint 11 introduced new data models (DatasetMetadata, TransformationConfig, ModelConfig) and data versioning. Sprint 12 integrated these models with the API layer. However, **no E2E tests exist** to validate:

1. Complete user workflows with new architecture
2. Frontend ↔ Backend integration with new endpoints
3. Live AI recommendations working end-to-end
4. Data versioning functionality in real browser environment
5. Production-ready system behavior

**Without E2E testing, we risk deploying broken integration between frontend and backend.**

---

## Acceptance Criteria

### Backend Integration Tests
- [ ] API integration tests for DatasetMetadata endpoints
- [ ] API integration tests for TransformationConfig endpoints
- [ ] API integration tests for ModelConfig endpoints
- [ ] API integration tests for versioning endpoints
- [ ] Backend tests pass with >95% coverage

### Frontend E2E Tests (Playwright)
- [ ] E2E test for upload workflow with new DatasetMetadata model
- [ ] E2E test for transformation workflow with TransformationConfig
- [ ] E2E test for model training workflow with ModelConfig
- [ ] E2E test for data versioning UI (create, compare, lineage)
- [ ] E2E test for live AI recommendations on sample data
- [ ] E2E test for complete workflow: upload → transform → train → predict with AI guidance

### Production Readiness Validation
- [ ] All critical workflows complete successfully in browser
- [ ] AI recommendations display correctly
- [ ] No console errors or warnings
- [ ] Performance metrics within acceptable range (<5s page loads)
- [ ] All E2E tests passing on Chromium

---

## Technical Tasks

### Task 12.5.1: Backend API Integration Tests (3h)

**Objective**: Test complete API flows with real HTTP requests and database

**Files to Create/Update:**
- `apps/backend/tests/integration/test_dataset_api_integration.py` (new)
- `apps/backend/tests/integration/test_transformation_api_integration.py` (new)
- `apps/backend/tests/integration/test_model_api_integration.py` (new)
- `apps/backend/tests/integration/test_versioning_api_integration.py` (new)

**Test Scenarios:**

1. **Dataset API Integration** (1h)
   - Upload CSV → Create DatasetMetadata → Verify S3 storage
   - Retrieve dataset → Validate metadata structure
   - List datasets → Verify DatasetMetadata collection query
   - Update dataset metadata → Verify persistence
   - Test backward compatibility with legacy UserData endpoints

2. **Transformation API Integration** (1h)
   - Preview transformation → Create TransformationConfig
   - Apply transformation → Create new dataset version
   - Retrieve transformation history → Verify lineage tracking
   - Test transformation validation with invalid data
   - Verify transformation preview accuracy

3. **Model Training API Integration** (1h)
   - Train model → Create ModelConfig with performance metrics
   - Retrieve model → Validate ModelConfig structure
   - Deploy model → Update deployment status
   - Make predictions → Verify prediction service integration
   - Test model versioning (multiple training runs)

4. **Versioning API Integration** (0.5h)
   - Create dataset version → Verify version metadata
   - Retrieve version history → Validate lineage chain
   - Compare versions → Verify diff generation
   - Test version parent/child relationships

**Success Metrics:**
- All backend integration tests passing
- >95% code coverage for new API endpoints
- No MongoDB connection issues
- Tests complete in <60 seconds

---

### Task 12.5.2: Frontend E2E Workflow Tests (3h)

**Objective**: Test complete user workflows in real browser with Playwright

**Files to Create/Update:**
- `apps/frontend/e2e/workflows/dataset-metadata.spec.ts` (new)
- `apps/frontend/e2e/workflows/transformation-config.spec.ts` (new)
- `apps/frontend/e2e/workflows/model-config.spec.ts` (new)
- `apps/frontend/e2e/workflows/data-versioning.spec.ts` (new)
- `apps/frontend/e2e/workflows/complete-ai-workflow.spec.ts` (new)

**Test Scenarios:**

1. **Dataset Upload with New Models** (0.5h)
   ```typescript
   test('@smoke Upload CSV and verify DatasetMetadata', async ({ authenticatedPage }) => {
     // Upload sample CSV
     await uploadPage.uploadFile('test-data/iris.csv');
     await uploadPage.waitForUploadComplete();

     // Verify DatasetMetadata structure in API response
     const metadata = await getDatasetMetadata(datasetId);
     expect(metadata.schema_info).toBeDefined();
     expect(metadata.quality_metrics).toBeDefined();
     expect(metadata.version_info.version).toBe(1);

     // Verify UI displays metadata correctly
     await expect(page.locator('[data-testid="dataset-rows"]')).toHaveText('150');
     await expect(page.locator('[data-testid="dataset-columns"]')).toHaveText('5');
   });
   ```

2. **Transformation Workflow with AI Recommendations** (1h)
   ```typescript
   test('@smoke Transform data with AI suggestions', async ({ authenticatedPage }) => {
     // Upload and navigate to transformations
     const datasetId = await uploadTestDataset('titanic.csv');
     await page.goto(`/datasets/${datasetId}/transform`);

     // Wait for AI recommendations
     await expect(page.locator('[data-testid="ai-recommendations"]')).toBeVisible();

     // Verify AI suggestions display
     const suggestions = await page.locator('[data-testid="suggestion-card"]').count();
     expect(suggestions).toBeGreaterThan(0);

     // Apply AI-recommended transformation
     await page.locator('[data-testid="suggestion-0"]').click();
     await page.locator('[data-testid="apply-transformation"]').click();

     // Verify TransformationConfig created
     const config = await getTransformationConfig(transformationId);
     expect(config.operations).toBeDefined();
     expect(config.preview_available).toBe(true);

     // Verify new dataset version created
     await expect(page.locator('[data-testid="dataset-version"]')).toHaveText('v2');
   });
   ```

3. **Model Training with ModelConfig** (0.75h)
   ```typescript
   test('@smoke Train model and verify ModelConfig', async ({ authenticatedPage }) => {
     // Upload and transform data
     const datasetId = await prepareDatasetForTraining();
     await page.goto(`/datasets/${datasetId}/train`);

     // Wait for AI problem detection
     await expect(page.locator('[data-testid="problem-type"]')).toBeVisible();

     // Verify AI detected problem type correctly
     await expect(page.locator('[data-testid="problem-type"]')).toHaveText('Classification');

     // Select target column and train
     await page.selectOption('[data-testid="target-column"]', 'species');
     await page.click('[data-testid="train-model"]');

     // Wait for training completion
     await page.waitForSelector('[data-testid="training-complete"]', { timeout: 60000 });

     // Verify ModelConfig structure
     const modelConfig = await getModelConfig(modelId);
     expect(modelConfig.problem_type).toBe('classification');
     expect(modelConfig.performance_metrics).toBeDefined();
     expect(modelConfig.feature_importance).toBeDefined();

     // Verify UI displays performance metrics
     await expect(page.locator('[data-testid="accuracy"]')).toBeVisible();
   });
   ```

4. **Data Versioning UI** (0.75h)
   ```typescript
   test('Create and compare dataset versions', async ({ authenticatedPage }) => {
     // Create initial dataset
     const datasetId = await uploadTestDataset('sales.csv');

     // Apply transformation to create v2
     await applyTransformation(datasetId, 'fillna');

     // Navigate to versions page
     await page.goto(`/datasets/${datasetId}/versions`);

     // Verify version list displays
     await expect(page.locator('[data-testid="version-1"]')).toBeVisible();
     await expect(page.locator('[data-testid="version-2"]')).toBeVisible();

     // Compare versions
     await page.click('[data-testid="compare-versions"]');
     await page.selectOption('[data-testid="version-a"]', '1');
     await page.selectOption('[data-testid="version-b"]', '2');
     await page.click('[data-testid="run-comparison"]');

     // Verify comparison results
     await expect(page.locator('[data-testid="version-diff"]')).toBeVisible();
     await expect(page.locator('[data-testid="lineage-diagram"]')).toBeVisible();
   });
   ```

5. **Complete AI-Guided Workflow** (1h)
   ```typescript
   test('@smoke Complete workflow: Upload → Transform → Train → Predict with AI', async ({ authenticatedPage }) => {
     // Step 1: Upload
     await page.goto('/datasets/upload');
     await uploadPage.uploadFile('test-data/housing.csv');
     const datasetId = await uploadPage.getDatasetId();

     // Step 2: AI Analysis
     await page.waitForSelector('[data-testid="ai-analysis-complete"]');
     const insights = await page.locator('[data-testid="ai-insight"]').allTextContents();
     expect(insights.length).toBeGreaterThan(0);

     // Step 3: AI-Guided Transformations
     await page.click('[data-testid="view-recommendations"]');
     await expect(page.locator('[data-testid="recommended-transformations"]')).toBeVisible();

     // Apply top 3 recommendations
     for (let i = 0; i < 3; i++) {
       await page.click(`[data-testid="apply-recommendation-${i}"]`);
       await page.waitForSelector(`[data-testid="transformation-applied-${i}"]`);
     }

     // Step 4: Model Training with AI-detected problem type
     await page.goto(`/datasets/${datasetId}/train`);
     await expect(page.locator('[data-testid="ai-problem-detection"]')).toHaveText(/regression|classification/i);

     // Train with default AI suggestions
     await page.click('[data-testid="train-with-ai-config"]');
     await page.waitForSelector('[data-testid="training-complete"]', { timeout: 120000 });

     // Step 5: Predictions
     await page.click('[data-testid="make-predictions"]');
     await uploadPage.uploadFile('test-data/housing_test.csv');
     await page.waitForSelector('[data-testid="predictions-ready"]');

     // Verify predictions display
     const predictions = await page.locator('[data-testid="prediction-row"]').count();
     expect(predictions).toBeGreaterThan(0);

     // Step 6: Download results
     await page.click('[data-testid="download-predictions"]');
     const download = await page.waitForEvent('download');
     expect(download.suggestedFilename()).toMatch(/predictions.*\.csv/);
   });
   ```

**Success Metrics:**
- All E2E workflow tests passing on Chromium
- Tests complete in <10 minutes
- No console errors during test execution
- Screenshots/videos captured for failures

---

### Task 12.5.3: AI Recommendation Validation Tests (1.5h)

**Objective**: Validate live AI recommendations work correctly with sample data

**Files to Create/Update:**
- `apps/frontend/e2e/workflows/ai-recommendations.spec.ts` (new)
- `apps/frontend/e2e/test-data/ai-test-datasets/` (new directory)

**Test Datasets:**
- `iris.csv` - Classification problem (3 classes)
- `housing.csv` - Regression problem
- `titanic.csv` - Binary classification with missing values
- `sales.csv` - Time series regression
- `customer-churn.csv` - Imbalanced classification

**Test Scenarios:**

1. **AI Problem Type Detection** (0.5h)
   - Upload each test dataset
   - Verify AI correctly detects problem type
   - Validate confidence scores displayed
   - Test edge cases (ambiguous datasets)

2. **AI Transformation Recommendations** (0.5h)
   - Test recommendations for missing values
   - Test recommendations for categorical encoding
   - Test recommendations for feature engineering
   - Verify recommendations are actionable
   - Test recommendation explanations display

3. **AI Model Suggestions** (0.5h)
   - Verify AI suggests appropriate algorithms
   - Test algorithm performance estimates
   - Validate hyperparameter recommendations
   - Test ensemble model suggestions

**Success Metrics:**
- AI recommendations appear within 5 seconds
- Problem type detection >90% accuracy on test datasets
- All recommendation types tested
- No AI service errors

---

### Task 12.5.4: Performance and Production Validation (0.5h)

**Objective**: Validate system meets performance targets and is production-ready

**Performance Tests:**
- Page load time <5 seconds
- Dataset upload <10 seconds for 10MB file
- Transformation preview <3 seconds
- Model training <2 minutes for small dataset (150 rows)
- Prediction latency <100ms per row

**Production Readiness Checks:**
- No console errors in browser
- No unhandled promise rejections
- All API responses include proper headers
- Error messages are user-friendly
- Loading states display correctly
- Accessibility: All interactive elements keyboard-navigable

**Files to Create/Update:**
- `apps/frontend/e2e/workflows/performance.spec.ts` (new)
- `apps/frontend/e2e/workflows/production-readiness.spec.ts` (new)

---

## Dependencies

**Blocks:**
- Story 12.1 (API Integration) - Must be complete ✅
- Story 12.2 (Data Versioning API) - Must be complete ✅
- Story 12.3 (Service Layer Refactoring) - Must be complete ✅

**Required Infrastructure:**
- MongoDB test instance running
- Redis test instance running
- LocalStack (S3) running
- OpenAI API key configured (can be mocked)
- Frontend dev server running
- Backend API server running

**Test Data:**
- Sample datasets in `apps/frontend/e2e/test-data/`
- Test user credentials configured
- Test S3 bucket created

---

## Risks and Mitigation

### Risk: E2E tests are flaky
**Mitigation:**
- Use Playwright's auto-waiting mechanisms
- Implement retry logic for AI API calls
- Add explicit waits for AI processing
- Use data-testid attributes for stable selectors

### Risk: AI recommendations are slow/timeout
**Mitigation:**
- Set appropriate timeouts (60-120 seconds)
- Add loading state validation
- Implement fallback UI for slow responses
- Mock AI responses in CI environment if needed

### Risk: Tests take too long
**Mitigation:**
- Run smoke tests (@smoke) in CI
- Run full suite nightly or on main branch
- Parallelize tests across multiple workers
- Optimize test data size

### Risk: Integration with new models breaks existing features
**Mitigation:**
- Include regression tests for old workflows
- Test backward compatibility endpoints
- Validate legacy UserData endpoints still work
- Monitor for breaking changes in API contracts

---

## Success Metrics

### Coverage Metrics
- Backend integration tests: >95% coverage
- Frontend E2E tests: All critical workflows covered
- AI recommendations: All recommendation types tested

### Quality Metrics
- All tests passing on Chromium
- <5% flakiness rate
- No production-blocking issues found
- Performance targets met

### Time Metrics
- Backend integration tests: <60 seconds
- Frontend smoke tests: <7 minutes
- Frontend full suite: <30 minutes

---

## Testing Strategy

### Development (Local)
```bash
# Start test services
cd apps/backend
docker-compose -f docker-compose.test.yml up -d

# Run backend integration tests
PYTHONPATH=. uv run pytest tests/integration/ -v -m integration

# Start dev servers
cd apps/backend && uv run uvicorn app.main:app --reload &
cd apps/frontend && npm run dev &

# Run frontend smoke tests
cd apps/frontend
npm run test:e2e:smoke
```

### CI/CD (GitHub Actions)
```yaml
# Pull Requests: Smoke tests only
- Backend integration tests (stories 12.1-12.3)
- Frontend E2E smoke tests (@smoke tagged)
- Duration: ~10 minutes

# Main Branch: Full suite
- All backend integration tests
- All frontend E2E tests
- Performance validation
- Duration: ~30 minutes
```

---

## Deliverables

### Test Files
- [ ] Backend API integration tests (4 files)
- [ ] Frontend E2E workflow tests (5 files)
- [ ] AI recommendation tests (1 file)
- [ ] Performance tests (1 file)
- [ ] Production readiness tests (1 file)

### Test Data
- [ ] AI test datasets (5 CSV files)
- [ ] Test fixtures for versioning scenarios
- [ ] Mock AI responses for CI

### Documentation
- [ ] Update TEST_INFRASTRUCTURE.md with new integration tests
- [ ] Update E2E README with new workflow tests
- [ ] Add troubleshooting guide for E2E setup
- [ ] Document AI testing best practices

### CI/CD
- [ ] Update GitHub Actions workflow for integration tests
- [ ] Configure test services in CI
- [ ] Set up test result reporting
- [ ] Configure failure notifications

---

## Completion Checklist

- [ ] All backend integration tests passing
- [ ] All frontend E2E tests passing
- [ ] AI recommendations validated on sample data
- [ ] Performance targets met
- [ ] Production readiness validated
- [ ] Tests running in CI/CD
- [ ] Documentation updated
- [ ] Test coverage >95%
- [ ] No flaky tests
- [ ] Team demo completed

---

**Story Points Breakdown:**
- Backend integration tests: 3 points
- Frontend E2E workflow tests: 3 points
- AI recommendation validation: 1.5 points
- Performance validation: 0.5 points

**Total**: 8 story points

**Estimated Time**: 8 hours

**Priority**: 🔴 CRITICAL - Without E2E testing, we cannot confidently deploy Sprint 11/12 changes to production.

---

**Related Documentation:**
- [Sprint 12 Plan](./SPRINT_12.md)
- [Test Infrastructure Guide](./apps/backend/docs/TEST_INFRASTRUCTURE.md)
- [E2E Testing README](./apps/frontend/e2e/README.md)
- [Integration Tests README](./apps/backend/tests/integration/README.md)
