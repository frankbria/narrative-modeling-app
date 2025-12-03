/**
 * Console Error Collector Helper
 * Monitors and collects console errors and warnings during E2E tests
 */

import { Page, ConsoleMessage } from '@playwright/test';

export interface ConsoleError {
  type: 'error' | 'warning' | 'info' | 'log';
  message: string;
  location?: string;
  stackTrace?: string;
  timestamp: string;
}

export interface PageError {
  message: string;
  name: string;
  stack?: string;
  timestamp: string;
}

export class ConsoleErrorCollector {
  private consoleMessages: ConsoleError[] = [];
  private pageErrors: PageError[] = [];
  private page: Page;
  private listeners: Array<() => void> = [];

  constructor(page: Page) {
    this.page = page;
    this.attachListeners();
  }

  /**
   * Attach console and page error listeners
   */
  private attachListeners(): void {
    // Listen to console messages
    const consoleListener = (msg: ConsoleMessage) => {
      const type = msg.type() as ConsoleError['type'];

      // Filter out noise (debug, verbose logs)
      if (['error', 'warning'].includes(type)) {
        const error: ConsoleError = {
          type,
          message: msg.text(),
          location: msg.location()?.url,
          timestamp: new Date().toISOString(),
        };

        this.consoleMessages.push(error);
      }
    };

    this.page.on('console', consoleListener);
    this.listeners.push(() => this.page.off('console', consoleListener));

    // Listen to page errors (uncaught exceptions)
    const pageErrorListener = (error: Error) => {
      const pageError: PageError = {
        message: error.message,
        name: error.name,
        stack: error.stack,
        timestamp: new Date().toISOString(),
      };

      this.pageErrors.push(pageError);
    };

    this.page.on('pageerror', pageErrorListener);
    this.listeners.push(() => this.page.off('pageerror', pageErrorListener));
  }

  /**
   * Get all console errors
   */
  getConsoleErrors(): ConsoleError[] {
    return this.consoleMessages.filter((m) => m.type === 'error');
  }

  /**
   * Get all console warnings
   */
  getConsoleWarnings(): ConsoleError[] {
    return this.consoleMessages.filter((m) => m.type === 'warning');
  }

  /**
   * Get all page errors
   */
  getPageErrors(): PageError[] {
    return [...this.pageErrors];
  }

  /**
   * Get all errors (console + page)
   */
  getAllErrors(): Array<ConsoleError | PageError> {
    return [...this.getConsoleErrors(), ...this.pageErrors];
  }

  /**
   * Check if any errors occurred
   */
  hasErrors(): boolean {
    return this.getConsoleErrors().length > 0 || this.pageErrors.length > 0;
  }

  /**
   * Get error count
   */
  getErrorCount(): number {
    return this.getConsoleErrors().length + this.pageErrors.length;
  }

  /**
   * Get warning count
   */
  getWarningCount(): number {
    return this.getConsoleWarnings().length;
  }

  /**
   * Filter errors by pattern
   */
  filterErrors(pattern: string | RegExp): Array<ConsoleError | PageError> {
    const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;

    return this.getAllErrors().filter((error) =>
      regex.test(error.message)
    );
  }

  /**
   * Check if specific error exists
   */
  hasErrorMatching(pattern: string | RegExp): boolean {
    return this.filterErrors(pattern).length > 0;
  }

  /**
   * Clear all collected errors
   */
  clearErrors(): void {
    this.consoleMessages = [];
    this.pageErrors = [];
  }

  /**
   * Get formatted error report
   */
  getErrorReport(): string {
    const report: string[] = [];

    report.push('=== Console Error Report ===\n');

    if (this.pageErrors.length > 0) {
      report.push(`Page Errors (${this.pageErrors.length}):`);
      this.pageErrors.forEach((error, index) => {
        report.push(`  ${index + 1}. [${error.name}] ${error.message}`);
        if (error.stack) {
          report.push(`     Stack: ${error.stack.split('\n')[0]}`);
        }
      });
      report.push('');
    }

    const consoleErrors = this.getConsoleErrors();
    if (consoleErrors.length > 0) {
      report.push(`Console Errors (${consoleErrors.length}):`);
      consoleErrors.forEach((error, index) => {
        report.push(`  ${index + 1}. ${error.message}`);
        if (error.location) {
          report.push(`     Location: ${error.location}`);
        }
      });
      report.push('');
    }

    const warnings = this.getConsoleWarnings();
    if (warnings.length > 0) {
      report.push(`Console Warnings (${warnings.length}):`);
      warnings.forEach((warning, index) => {
        report.push(`  ${index + 1}. ${warning.message}`);
      });
    }

    if (!this.hasErrors() && warnings.length === 0) {
      report.push('No errors or warnings detected.');
    }

    return report.join('\n');
  }

  /**
   * Assert no errors occurred
   */
  assertNoErrors(allowedPatterns: Array<string | RegExp> = []): void {
    const errors = this.getAllErrors();

    // Filter out allowed errors
    const filteredErrors = errors.filter((error) => {
      return !allowedPatterns.some((pattern) => {
        const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;
        return regex.test(error.message);
      });
    });

    if (filteredErrors.length > 0) {
      throw new Error(
        `Expected no console errors, but found ${filteredErrors.length}:\n${this.getErrorReport()}`
      );
    }
  }

  /**
   * Cleanup listeners
   */
  cleanup(): void {
    this.listeners.forEach((remove) => remove());
    this.listeners = [];
  }

  /**
   * Create a snapshot of current errors
   */
  createSnapshot(): {
    consoleMessages: ConsoleError[];
    pageErrors: PageError[];
  } {
    return {
      consoleMessages: [...this.consoleMessages],
      pageErrors: [...this.pageErrors],
    };
  }

  /**
   * Compare snapshots to find new errors
   */
  getNewErrors(snapshot: {
    consoleMessages: ConsoleError[];
    pageErrors: PageError[];
  }): Array<ConsoleError | PageError> {
    const newConsoleErrors = this.consoleMessages.slice(
      snapshot.consoleMessages.length
    );
    const newPageErrors = this.pageErrors.slice(snapshot.pageErrors.length);

    return [...newConsoleErrors, ...newPageErrors];
  }
}
