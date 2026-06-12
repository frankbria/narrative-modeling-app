import { Page } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Upload Page Object
 * Handles dataset upload interactions
 */
export class UploadPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Upload a file and click the upload button
   */
  async uploadFile(filePath: string) {
    const fileInput = this.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);

    // Wait for the upload button to appear and click it
    const uploadButton = this.page.getByTestId('upload-button');
    await uploadButton.waitFor({ state: 'visible', timeout: 5000 });
    await uploadButton.click();
  }

  /**
   * Wait for upload to complete: the success panel must be visible AND carry
   * the stored file ID (mirrors the uploadTestDataset fixture's success
   * detection — success text alone can render before the ID is populated).
   */
  async waitForUploadComplete() {
    await this.waitForElement('text=/uploaded successfully|File uploaded/i');
    await this.page.getByTestId('file-id').waitFor({ state: 'visible', timeout: 10000 });
  }

  /**
   * Click the post-upload "Next Step" button and wait for navigation
   * to the dataset's explore page (/explore/{id}). The explore page
   * stage-gates on workflow state and can redirect back to /upload, so
   * also wait for its dataset heading before returning.
   */
  async continueToExplore() {
    const nextStepButton = this.page.getByTestId('next-step-button');
    await nextStepButton.waitFor({ state: 'visible', timeout: 10000 });
    await nextStepButton.click();
    await this.page.waitForURL(/\/explore\/[a-zA-Z0-9-]+/, { timeout: 30000 });
    // The explore page's h1 is the dataset filename; excluding the upload
    // heading keeps this wait from matching /upload after a gating redirect
    await this.page
      .locator('h1')
      .filter({ hasNotText: 'Upload Your Data' })
      .first()
      .waitFor({ state: 'visible', timeout: 15000 });
    if (this.page.url().includes('/upload')) {
      throw new Error('continueToExplore: redirected back to /upload by workflow stage gating');
    }
  }

  /**
   * Check whether the inline upload error panel is visible
   */
  async hasUploadError(): Promise<boolean> {
    return await this.page.getByTestId('upload-error').isVisible();
  }

  /**
   * Get the dataset ID from the current URL
   */
  async getDatasetId(): Promise<string> {
    const url = this.page.url();
    // Match either /explore/[id] or /datasets/[id] patterns
    const match = url.match(/\/(explore|datasets)\/([a-zA-Z0-9-]+)/);

    if (!match) {
      throw new Error('Could not extract dataset ID from URL: ' + url);
    }

    return match[2]; // Return the ID (second capture group)
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(message: string): Promise<boolean> {
    return await this.isVisible(`text=${message}`);
  }
}
