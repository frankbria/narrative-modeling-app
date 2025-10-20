import { Page, Locator } from '@playwright/test';

/**
 * Base Page Object
 * Provides common functionality for all page objects
 */
export class BasePage {
  constructor(protected page: Page) {}

  /**
   * Navigate to a specific path
   */
  async goto(path: string) {
    await this.page.goto(path);
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Wait for an element to be visible
   */
  async waitForElement(selector: string, timeout: number = 30000) {
    await this.page.waitForSelector(selector, { timeout });
  }

  /**
   * Get a locator for a selector
   */
  locator(selector: string): Locator {
    return this.page.locator(selector);
  }

  /**
   * Click an element
   */
  async click(selector: string) {
    await this.locator(selector).click();
  }

  /**
   * Fill a form field
   */
  async fill(selector: string, value: string) {
    await this.locator(selector).fill(value);
  }

  /**
   * Get text content of an element
   */
  async getText(selector: string): Promise<string> {
    return (await this.locator(selector).textContent()) || '';
  }

  /**
   * Check if element is visible
   */
  async isVisible(selector: string): Promise<boolean> {
    try {
      return await this.locator(selector).isVisible({ timeout: 5000 });
    } catch {
      return false;
    }
  }

  /**
   * Wait for navigation
   */
  async waitForNavigation(urlPattern: string | RegExp) {
    await this.page.waitForURL(urlPattern);
  }
}
