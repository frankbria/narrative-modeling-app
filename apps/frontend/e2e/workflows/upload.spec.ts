/**
 * Upload Workflow E2E Tests
 *
 * Tests the complete dataset upload workflow including:
 * - Valid CSV file upload, progress, drag and drop, concurrent uploads
 * - Metadata storage verification
 * - PII detection and the masked copy
 * - An unparseable CSV is refused
 * - A CSV with a header and no rows is refused, with the backend's sentence (#1062)
 *
 * Coverage Target: >85%
 */

import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders } from '../helpers/apiAuth';
import { UploadPage } from '../pages/UploadPage';
import { join } from 'path';
import { readFileSync } from 'fs';

test.describe('Dataset Upload Workflow', () => {
  test('should upload valid CSV file successfully @smoke', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    // Navigate to upload page
    await uploadPage.goto('/upload');

    // Upload file
    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);

    // Wait for upload to complete
    await uploadPage.waitForUploadComplete();

    // Verify success message is displayed
    await expect(authenticatedPage.locator('text=/File uploaded successfully/i')).toBeVisible();
  });

  test('should verify metadata storage after upload @smoke', async ({ authenticatedPage, request }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    // Verify success message is displayed
    await expect(authenticatedPage.locator('text=/File uploaded successfully/i')).toBeVisible();

    // Navigate to the explore page via the Next Step button, then read the ID
    await uploadPage.continueToExplore();
    const datasetId = await uploadPage.getDatasetId();

    // The stored record, read from the backend itself as the signed-in user. This used
    // to be a relative /api/v1 URL, which never leaves the Next dev server, under an id
    // from the wrong id-space, with a branch that logged "skipped" on any failure: the
    // check had never run (#752).
    const stored = await request.get(`${API_BASE}/user_data/${datasetId}`, {
      headers: await apiAuthHeaders(request),
    });
    expect(stored.status()).toBe(200);
    const record = await stored.json();
    expect(record.filename).toContain('sample');
    expect(record.num_rows).toBeGreaterThan(0);
    expect(record.num_columns).toBeGreaterThan(0);
    expect(record.s3_url).toBeTruthy();
  });

  test('should detect and display schema information', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    // The current upload UI surfaces the inferred schema as the Preview Data
    // table: column headers from the file plus example rows. It does not
    // render dtype labels (numeric/categorical/...) on this page.
    await expect(authenticatedPage.locator('text=Preview Data')).toBeVisible({ timeout: 10000 });
    for (const column of ['age', 'income', 'purchased']) {
      await expect(
        authenticatedPage.locator('th', { hasText: column })
      ).toBeVisible();
    }
  });

  test('should handle concurrent uploads', async ({ context, request }) => {
    // Create two pages for concurrent uploads
    const page1 = await context.newPage();
    const page2 = await context.newPage();

    const uploadPage1 = new UploadPage(page1);
    const uploadPage2 = new UploadPage(page2);

    try {
      // Navigate both pages to upload
      await Promise.all([uploadPage1.goto('/upload'), uploadPage2.goto('/upload')]);

      // Start both uploads simultaneously
      const csvPath = join(__dirname, '../test-data/sample.csv');
      await Promise.all([uploadPage1.uploadFile(csvPath), uploadPage2.uploadFile(csvPath)]);

      // Wait for both to complete
      await Promise.all([
        uploadPage1.waitForUploadComplete(),
        uploadPage2.waitForUploadComplete(),
      ]);

      // Verify both uploads succeeded
      await expect(page1.locator('text=/Upload complete|sample.csv/')).toBeVisible();
      await expect(page2.locator('text=/Upload complete|sample.csv/')).toBeVisible();
    } finally {
      await page1.close();
      await page2.close();
    }
  });

  test('should display upload progress indicator @smoke', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');

    // Set file on input
    const fileInput = authenticatedPage.locator('input[type="file"]');
    await fileInput.setInputFiles(csvPath);

    // Click the upload button to start upload
    const uploadButton = authenticatedPage.getByTestId('upload-button');
    await uploadButton.waitFor({ state: 'visible', timeout: 5000 });
    await uploadButton.click();

    // Verify progress indicator appears (button text changes during upload).
    // Target the button itself — a bare text locator also matches the static
    // page copy ("Start by uploading...") and trips strict mode.
    await expect(
      authenticatedPage.getByTestId('upload-button')
    ).toHaveText(/Scanning|Uploading|Processing/i, { timeout: 5000 });

    // Wait for completion
    await uploadPage.waitForUploadComplete();

    // Verify completion message
    await expect(
      authenticatedPage.locator('text=/File uploaded successfully/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should support drag and drop upload', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/upload');

    const dropzone = authenticatedPage.getByTestId('upload-dropzone');
    await dropzone.waitFor({ state: 'visible', timeout: 10000 });

    // Simulate a real drag-and-drop: react-dropzone's onDrop fires on the
    // drop event with a DataTransfer payload (not on input file selection).
    const csvPath = join(__dirname, '../test-data/sample.csv');
    const csvContent = readFileSync(csvPath).toString();
    const dataTransfer = await authenticatedPage.evaluateHandle(
      ({ data, name }) => {
        const dt = new DataTransfer();
        dt.items.add(new File([data], name, { type: 'text/csv' }));
        return dt;
      },
      { data: csvContent, name: 'sample.csv' }
    );
    await dropzone.dispatchEvent('drop', { dataTransfer });

    // Dropped file is reflected in the dropzone, then upload proceeds
    await expect(authenticatedPage.locator('text=sample.csv').first()).toBeVisible({ timeout: 5000 });
    await authenticatedPage.getByTestId('upload-button').click();
    await uploadPage.waitForUploadComplete();
  });

  test('should preserve uploaded files across page refreshes', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();
    await uploadPage.continueToExplore();

    // The post-upload URL (/explore/{id}) is where the dataset ID lives;
    // there is no standalone /datasets/{id} detail route in the current app
    const datasetId = await uploadPage.getDatasetId();

    // Refresh: workflow state persists in localStorage, so the explore page
    // must not stage-gate back to /upload and the dataset must reload
    await authenticatedPage.reload();

    await expect(
      authenticatedPage.locator('h1', { hasText: 'sample.csv' })
    ).toBeVisible({ timeout: 15000 });
    expect(authenticatedPage.url()).toContain(`/explore/${datasetId}`);
  });

  test('should display data preview after successful upload', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    // Verify data preview table is visible
    await expect(authenticatedPage.locator('table, [data-testid="data-preview"]')).toBeVisible({ timeout: 10000 });

    // Verify column headers from sample.csv
    await expect(authenticatedPage.locator('th:has-text("age")')).toBeVisible({ timeout: 5000 });
    await expect(authenticatedPage.locator('th:has-text("income")')).toBeVisible({ timeout: 5000 });
    await expect(authenticatedPage.locator('th:has-text("purchased")')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Upload Security and Validation', () => {
  test('warns about high-risk PII and stores the masked copy once chosen', async ({
    authenticatedPage,
    cleanupDataset,
  }) => {
    // The page crashed on this warning for every high-risk file (#1054).
    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/upload');
    await uploadPage.uploadFile(join(__dirname, '../test-data/data-with-pii.csv'));

    await expect(authenticatedPage.getByText('Sensitive Data Detected')).toBeVisible({ timeout: 30000 });
    await expect(authenticatedPage.getByText('Columns With PII')).toBeVisible();
    await authenticatedPage.getByRole('button', { name: /upload with data masking/i }).click();

    await uploadPage.waitForUploadComplete();
    const datasetId = ((await authenticatedPage.getByTestId('file-id').textContent()) ?? '').replace('File ID:', '').trim();
    expect(datasetId).toMatch(/^[a-f0-9]{24}$/);
    await cleanupDataset(datasetId);
  });

  test('should show an error for a CSV it cannot parse', async ({ authenticatedPage: page }) => {
    // A row with more fields than the header has.
    await page.goto('/upload');
    await page.getByTestId('file-input').setInputFiles({
      name: 'ragged.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('name,age\nada,36\nbob,41,extra,fields\n'),
    });
    await page.getByTestId('upload-button').click();

    await expect(page.getByTestId('upload-error')).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('upload-status')).toBeHidden();
  });

  test('should refuse a CSV with a header and no rows, saying so', async ({ authenticatedPage: page }) => {
    await page.goto('/upload');
    await page.getByTestId('file-input').setInputFiles({
      name: 'header-only.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('name,age\n'),
    });
    await page.getByTestId('upload-button').click();

    await expect(page.getByTestId('upload-error-message')).toContainText('no data rows', { timeout: 30000 });
    await expect(page.getByTestId('upload-status')).toBeHidden();
  });
});
