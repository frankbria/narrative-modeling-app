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
   * Upload a file
   */
  async uploadFile(filePath: string) {
    const fileInput = this.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
  }

  /**
   * Wait for upload to complete
   */
  async waitForUploadComplete() {
    await this.waitForElement('text=/Upload (complete|successful)/i');
  }

  /**
   * Get the dataset ID from the current URL
   */
  async getDatasetId(): Promise<string> {
    const url = this.page.url();
    const match = url.match(/\/datasets\/([a-zA-Z0-9-]+)/);

    if (!match) {
      throw new Error('Could not extract dataset ID from URL: ' + url);
    }

    return match[1];
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(message: string): Promise<boolean> {
    return await this.isVisible(`text=${message}`);
  }
}
