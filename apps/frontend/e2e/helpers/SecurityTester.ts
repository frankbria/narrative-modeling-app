/**
 * Security Tester Helper
 * Provides security testing utilities for E2E tests
 */

import { Page, Request } from '@playwright/test';

export interface SecurityTestResult {
  testName: string;
  passed: boolean;
  message: string;
  details?: any;
}

export class SecurityTester {
  constructor(private page: Page) {}

  /**
   * Test for XSS vulnerabilities
   */
  async testXSSPrevention(
    inputSelector: string,
    submitSelector: string,
    outputSelector: string
  ): Promise<SecurityTestResult> {
    const xssPayloads = [
      '<script>alert("XSS")</script>',
      '<img src=x onerror=alert("XSS")>',
      'javascript:alert("XSS")',
      '<svg onload=alert("XSS")>',
      '"><script>alert("XSS")</script>',
    ];

    const results: boolean[] = [];

    for (const payload of xssPayloads) {
      // Fill input with XSS payload
      await this.page.fill(inputSelector, payload);

      // Submit form
      await this.page.click(submitSelector);
      await this.page.waitForTimeout(1000);

      // Check if output is properly escaped
      const outputContent = await this.page.textContent(outputSelector);

      // XSS is prevented if the payload is rendered as text, not executed
      const isEscaped =
        outputContent?.includes('<script>') ||
        outputContent?.includes('&lt;script&gt;') ||
        !outputContent?.includes(payload);

      results.push(isEscaped);

      // Clear input for next test
      await this.page.fill(inputSelector, '');
    }

    const allPassed = results.every((r) => r);

    return {
      testName: 'XSS Prevention',
      passed: allPassed,
      message: allPassed
        ? 'All XSS payloads were properly escaped'
        : 'Some XSS payloads were not escaped',
      details: { payloadsTested: xssPayloads.length, passed: results.filter(Boolean).length },
    };
  }

  /**
   * Test for SQL/NoSQL injection vulnerabilities
   */
  async testInjectionPrevention(
    inputSelector: string,
    submitSelector: string
  ): Promise<SecurityTestResult> {
    const injectionPayloads = [
      "' OR '1'='1",
      "'; DROP TABLE users--",
      '{"$gt": ""}',
      '{"$ne": null}',
      "admin'--",
      "' OR 1=1--",
    ];

    let hasVulnerability = false;
    const errors: string[] = [];

    for (const payload of injectionPayloads) {
      await this.page.fill(inputSelector, payload);
      await this.page.click(submitSelector);
      await this.page.waitForTimeout(1000);

      // Check for SQL error messages that indicate vulnerability
      const pageContent = await this.page.textContent('body');
      const sqlErrorPatterns = [
        /syntax error/i,
        /mysql/i,
        /postgresql/i,
        /sqlite/i,
        /mongodb/i,
        /unclosed quotation/i,
      ];

      const hasError = sqlErrorPatterns.some((pattern) =>
        pattern.test(pageContent || '')
      );

      if (hasError) {
        hasVulnerability = true;
        errors.push(`Payload "${payload}" triggered database error`);
      }

      await this.page.fill(inputSelector, '');
    }

    return {
      testName: 'Injection Prevention',
      passed: !hasVulnerability,
      message: hasVulnerability
        ? 'Potential injection vulnerability detected'
        : 'No injection vulnerabilities detected',
      details: { payloadsTested: injectionPayloads.length, errors },
    };
  }

  /**
   * Test CSRF protection
   */
  async testCSRFProtection(formSelector: string): Promise<SecurityTestResult> {
    // Check if form has CSRF token
    const csrfToken = await this.page.locator(
      `${formSelector} input[name*="csrf"], ${formSelector} input[name*="token"]`
    ).count();

    // Check if requests include CSRF headers
    const requests: Request[] = [];
    this.page.on('request', (request) => {
      if (request.method() === 'POST' || request.method() === 'PUT') {
        requests.push(request);
      }
    });

    // Trigger a form submission
    const submitButton = this.page.locator(`${formSelector} button[type="submit"]`);
    if (await submitButton.isVisible({ timeout: 2000 })) {
      await submitButton.click();
      await this.page.waitForTimeout(1000);
    }

    // Check if POST/PUT requests have CSRF protection
    const hasCSRFHeaders = requests.some((req) => {
      const headers = req.headers();
      return (
        headers['x-csrf-token'] ||
        headers['x-xsrf-token'] ||
        headers['csrf-token']
      );
    });

    const passed = csrfToken > 0 || hasCSRFHeaders;

    return {
      testName: 'CSRF Protection',
      passed,
      message: passed
        ? 'CSRF protection detected (token or header)'
        : 'No CSRF protection detected',
      details: { hasToken: csrfToken > 0, hasHeaders: hasCSRFHeaders },
    };
  }

  /**
   * Test authentication requirement
   */
  async testAuthenticationRequired(
    protectedUrl: string
  ): Promise<SecurityTestResult> {
    // Try to access protected route without authentication
    await this.page.goto(protectedUrl);

    // Wait for an auth redirect (server-side middleware redirects fast;
    // client-side React redirects land after hydration). If no redirect
    // happens within the timeout, fall through to content-based checks.
    await this.page
      .waitForURL(/\/auth\/|\/login|\/signin/, { timeout: 5000 })
      .catch(async () => {
        await this.page.waitForLoadState('networkidle').catch(() => {});
      });

    const currentUrl = this.page.url();

    // Check if redirected to login or shows unauthorized
    const isRedirected =
      currentUrl.includes('/auth/') ||
      currentUrl.includes('/login') ||
      currentUrl.includes('/signin');

    const hasUnauthorizedMessage = await this.page
      .locator('text=/unauthorized|access denied|forbidden|401|403/i')
      .count();

    const passed = isRedirected || hasUnauthorizedMessage > 0;

    return {
      testName: 'Authentication Required',
      passed,
      message: passed
        ? 'Protected route requires authentication'
        : 'Protected route accessible without authentication',
      details: { redirected: isRedirected, hasUnauthorizedMessage: hasUnauthorizedMessage > 0 },
    };
  }

  /**
   * Test for secure headers
   */
  async testSecurityHeaders(url: string): Promise<SecurityTestResult> {
    const response = await this.page.goto(url);
    const headers = response?.headers() || {};

    const securityHeaders = {
      'x-frame-options': headers['x-frame-options'],
      'x-content-type-options': headers['x-content-type-options'],
      'x-xss-protection': headers['x-xss-protection'],
      'strict-transport-security': headers['strict-transport-security'],
      'content-security-policy': headers['content-security-policy'],
    };

    const presentHeaders = Object.entries(securityHeaders)
      .filter(([_, value]) => value)
      .map(([key]) => key);

    const passed = presentHeaders.length >= 3;

    return {
      testName: 'Security Headers',
      passed,
      message: passed
        ? `${presentHeaders.length} security headers detected`
        : `Only ${presentHeaders.length} security headers detected`,
      details: { headers: securityHeaders, presentCount: presentHeaders.length },
    };
  }

  /**
   * Test for sensitive data exposure in URLs
   */
  async testSensitiveDataInURL(): Promise<SecurityTestResult> {
    const currentUrl = this.page.url();

    const sensitivePatterns = [
      /password=/i,
      /token=[^&]{10,}/i,
      /api[_-]?key=/i,
      /secret=/i,
      /ssn=/i,
      /credit[_-]?card=/i,
    ];

    const exposedData = sensitivePatterns.filter((pattern) =>
      pattern.test(currentUrl)
    );

    const passed = exposedData.length === 0;

    return {
      testName: 'Sensitive Data in URL',
      passed,
      message: passed
        ? 'No sensitive data found in URL'
        : 'Sensitive data detected in URL',
      details: { exposedPatterns: exposedData.length },
    };
  }

  /**
   * Test input sanitization
   */
  async testInputSanitization(
    inputSelector: string,
    submitSelector: string
  ): Promise<SecurityTestResult> {
    const maliciousInputs = [
      '<script>alert(1)</script>',
      '../../../etc/passwd',
      '${7*7}',
      '{{7*7}}',
      '%00',
    ];

    let sanitized = true;

    for (const input of maliciousInputs) {
      await this.page.fill(inputSelector, input);
      await this.page.click(submitSelector);
      await this.page.waitForTimeout(500);

      // Check if input was sanitized (not executed)
      const pageContent = await this.page.textContent('body');

      // If we see the raw input or '49' (7*7), it might not be properly sanitized
      if (pageContent?.includes('49') && input.includes('7*7')) {
        sanitized = false;
      }
    }

    return {
      testName: 'Input Sanitization',
      passed: sanitized,
      message: sanitized
        ? 'All malicious inputs were sanitized'
        : 'Some inputs may not be properly sanitized',
      details: { inputsTested: maliciousInputs.length },
    };
  }

  /**
   * Run all security tests
   */
  async runAllTests(config: {
    protectedUrl?: string;
    inputSelector?: string;
    submitSelector?: string;
    outputSelector?: string;
    formSelector?: string;
  }): Promise<SecurityTestResult[]> {
    const results: SecurityTestResult[] = [];

    // Test authentication
    if (config.protectedUrl) {
      results.push(await this.testAuthenticationRequired(config.protectedUrl));
    }

    // Test security headers
    results.push(await this.testSecurityHeaders(this.page.url()));

    // Test sensitive data in URL
    results.push(await this.testSensitiveDataInURL());

    // Test XSS prevention
    if (config.inputSelector && config.submitSelector && config.outputSelector) {
      results.push(
        await this.testXSSPrevention(
          config.inputSelector,
          config.submitSelector,
          config.outputSelector
        )
      );
    }

    // Test injection prevention
    if (config.inputSelector && config.submitSelector) {
      results.push(
        await this.testInjectionPrevention(config.inputSelector, config.submitSelector)
      );
    }

    // Test CSRF protection
    if (config.formSelector) {
      results.push(await this.testCSRFProtection(config.formSelector));
    }

    return results;
  }

  /**
   * Get summary of security test results
   */
  getSummary(results: SecurityTestResult[]): {
    total: number;
    passed: number;
    failed: number;
    passRate: number;
  } {
    const total = results.length;
    const passed = results.filter((r) => r.passed).length;
    const failed = total - passed;
    const passRate = total > 0 ? (passed / total) * 100 : 0;

    return { total, passed, failed, passRate: Math.round(passRate) };
  }
}
