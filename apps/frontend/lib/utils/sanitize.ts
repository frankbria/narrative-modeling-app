/**
 * Sanitization utilities for user-controlled data
 * Provides defense-in-depth even though React escapes by default
 */

/** The text of a value; an object is stringified, or named as one when it cannot be. */
function stringify(value: unknown): string {
  if (typeof value !== 'object') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch (error) {
    return '[Complex Object]';
  }
}

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

  let stringValue = stringify(value);

  // Strip HTML tags (defense in depth). Any `<` left has no `>` after it, so what
  // remains cannot form a script element; the body of a stripped one stays as text.
  stringValue = stringValue.replace(/<[^>]*>/g, '');

  // Limit length to prevent DOM bloat
  if (stringValue.length > maxLength) {
    stringValue = stringValue.substring(0, maxLength) + '...';
  }

  return stringValue;
}
