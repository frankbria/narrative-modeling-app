/**
 * Performance Monitor Helper
 * Collects and logs performance metrics for E2E tests
 */

import { Page } from '@playwright/test';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';

export interface PerformanceMetric {
  testName: string;
  metricName: string;
  value: number;
  unit: string;
  timestamp: string;
  threshold?: number;
  passed?: boolean;
}

export class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private resultsPath: string;

  constructor(resultsPath?: string) {
    this.resultsPath =
      resultsPath || join(__dirname, '../performance-results.json');
  }

  /**
   * Measure Time to Interactive (TTI) for a page load
   */
  async measurePageLoad(
    page: Page,
    testName: string,
    url: string,
    threshold: number
  ): Promise<PerformanceMetric> {
    const startTime = Date.now();

    await page.goto(url);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;

    const metric: PerformanceMetric = {
      testName,
      metricName: `Page Load: ${url}`,
      value: loadTime,
      unit: 'ms',
      timestamp: new Date().toISOString(),
      threshold,
      passed: loadTime <= threshold,
    };

    this.metrics.push(metric);
    return metric;
  }

  /**
   * Measure API response time
   */
  async measureApiCall(
    testName: string,
    apiCall: () => Promise<any>,
    metricName: string,
    threshold: number
  ): Promise<PerformanceMetric> {
    const startTime = Date.now();

    await apiCall();

    const responseTime = Date.now() - startTime;

    const metric: PerformanceMetric = {
      testName,
      metricName,
      value: responseTime,
      unit: 'ms',
      timestamp: new Date().toISOString(),
      threshold,
      passed: responseTime <= threshold,
    };

    this.metrics.push(metric);
    return metric;
  }

  /**
   * Measure the p95 latency of an API call over many iterations (issue #152).
   *
   * Runs `apiCall` `iterations` times, sorts the durations, and records the
   * 95th-percentile value against `threshold`. Used for the beta-journey
   * "p95 API < 500ms" sanity check.
   */
  async measureP95(
    testName: string,
    apiCall: () => Promise<any>,
    metricName: string,
    threshold: number,
    iterations: number = 20
  ): Promise<PerformanceMetric> {
    const durations: number[] = [];

    for (let i = 0; i < iterations; i++) {
      const startTime = Date.now();
      await apiCall();
      durations.push(Date.now() - startTime);
    }

    durations.sort((a, b) => a - b);
    // Nearest-rank p95: index ceil(0.95 * n) - 1, clamped to the array.
    const rank = Math.ceil(0.95 * durations.length) - 1;
    const index = Math.min(durations.length - 1, Math.max(0, rank));
    const p95 = durations[index];

    const metric: PerformanceMetric = {
      testName,
      metricName: `p95 ${metricName}`,
      value: p95,
      unit: 'ms',
      timestamp: new Date().toISOString(),
      threshold,
      passed: p95 <= threshold,
    };

    this.metrics.push(metric);
    return metric;
  }

  /**
   * Measure rendering time for a specific element
   */
  async measureRenderTime(
    page: Page,
    testName: string,
    selector: string,
    metricName: string,
    threshold: number
  ): Promise<PerformanceMetric> {
    const startTime = Date.now();

    await page.waitForSelector(selector, { state: 'visible' });

    const renderTime = Date.now() - startTime;

    const metric: PerformanceMetric = {
      testName,
      metricName,
      value: renderTime,
      unit: 'ms',
      timestamp: new Date().toISOString(),
      threshold,
      passed: renderTime <= threshold,
    };

    this.metrics.push(metric);
    return metric;
  }

  /**
   * Measure concurrent operations average time
   */
  async measureConcurrentOperations(
    testName: string,
    operations: Array<() => Promise<any>>,
    metricName: string,
    threshold: number
  ): Promise<PerformanceMetric> {
    const startTimes: number[] = [];
    const endTimes: number[] = [];

    const promises = operations.map((op, index) => {
      startTimes[index] = Date.now();
      return op().then(() => {
        endTimes[index] = Date.now();
      });
    });

    await Promise.all(promises);

    const durations = endTimes.map((end, i) => end - startTimes[i]);
    const averageTime =
      durations.reduce((sum, d) => sum + d, 0) / durations.length;

    const metric: PerformanceMetric = {
      testName,
      metricName,
      value: Math.round(averageTime),
      unit: 'ms',
      timestamp: new Date().toISOString(),
      threshold,
      passed: averageTime <= threshold,
    };

    this.metrics.push(metric);
    return metric;
  }

  /**
   * Get performance timing from browser
   */
  async getBrowserTimings(page: Page): Promise<any> {
    return await page.evaluate(() => {
      const perf = performance.timing;
      return {
        navigationStart: perf.navigationStart,
        domContentLoadedEventEnd: perf.domContentLoadedEventEnd,
        loadEventEnd: perf.loadEventEnd,
        domInteractive: perf.domInteractive,
        domComplete: perf.domComplete,
        // Calculated metrics
        domLoadTime: perf.domContentLoadedEventEnd - perf.navigationStart,
        pageLoadTime: perf.loadEventEnd - perf.navigationStart,
        domInteractiveTime: perf.domInteractive - perf.navigationStart,
      };
    });
  }

  /**
   * Record a custom metric
   */
  recordMetric(
    testName: string,
    metricName: string,
    value: number,
    unit: string = 'ms',
    threshold?: number
  ): PerformanceMetric {
    const metric: PerformanceMetric = {
      testName,
      metricName,
      value,
      unit,
      timestamp: new Date().toISOString(),
      threshold,
      passed: threshold ? value <= threshold : undefined,
    };

    this.metrics.push(metric);
    return metric;
  }

  /**
   * Save all metrics to JSON file
   */
  saveMetrics(): void {
    let existingMetrics: PerformanceMetric[] = [];

    // Load existing metrics if file exists
    if (existsSync(this.resultsPath)) {
      try {
        const content = readFileSync(this.resultsPath, 'utf-8');
        existingMetrics = JSON.parse(content);
      } catch (error) {
        console.warn('Failed to read existing metrics:', error);
      }
    }

    // Append new metrics
    const allMetrics = [...existingMetrics, ...this.metrics];

    // Write to file
    writeFileSync(this.resultsPath, JSON.stringify(allMetrics, null, 2));
  }

  /**
   * Get summary of metrics
   */
  getSummary(): {
    total: number;
    passed: number;
    failed: number;
    avgValue: number;
  } {
    const total = this.metrics.length;
    const passed = this.metrics.filter((m) => m.passed === true).length;
    const failed = this.metrics.filter((m) => m.passed === false).length;
    const avgValue =
      this.metrics.reduce((sum, m) => sum + m.value, 0) / total || 0;

    return {
      total,
      passed,
      failed,
      avgValue: Math.round(avgValue),
    };
  }

  /**
   * Clear metrics
   */
  clearMetrics(): void {
    this.metrics = [];
  }

  /**
   * Get all metrics
   */
  getMetrics(): PerformanceMetric[] {
    return [...this.metrics];
  }
}
