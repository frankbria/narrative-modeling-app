/**
 * Sanitization utilities for user-controlled data
 * Provides defense-in-depth even though React escapes by default
 */

/**
 * Sanitize a value for safe display in the UI
 * Strips HTML tags and limits length to prevent DOM bloat
 *
 * @param value - The value to sanitize
 * @param maxLength - Maximum length (default: 1000)
 * @returns Sanitized string safe for display
 */
export function sanitizeForDisplay(value: unknown, maxLength: number = 1000): string {
  if (value === null || value === undefined) {
    return '';
  }

  let stringValue: string;

  // Handle objects by stringifying
  if (typeof value === 'object') {
    try {
      stringValue = JSON.stringify(value);
    } catch (error) {
      stringValue = '[Complex Object]';
    }
  } else {
    stringValue = String(value);
  }

  // Strip HTML tags (defense in depth)
  stringValue = stringValue.replace(/<[^>]*>/g, '');

  // Strip script tags specifically
  stringValue = stringValue.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

  // Limit length to prevent DOM bloat
  if (stringValue.length > maxLength) {
    stringValue = stringValue.substring(0, maxLength) + '...';
  }

  return stringValue;
}
