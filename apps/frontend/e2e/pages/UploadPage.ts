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
   * Wait for upload to complete
   */
  async waitForUploadComplete() {
    await this.waitForElement('text=/uploaded successfully|File uploaded/i');
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
