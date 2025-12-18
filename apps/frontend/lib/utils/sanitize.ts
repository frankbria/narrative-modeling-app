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

/**
 * Validate and sanitize a dataset ID
 * Only allows alphanumeric characters, hyphens, and underscores
 *
 * @param datasetId - The dataset ID to validate
 * @returns Validated dataset ID or null if invalid
 */
export function validateDatasetId(datasetId: string): string | null {
  if (!datasetId || typeof datasetId !== 'string') {
    return null;
  }

  // Only allow alphanumeric, hyphens, and underscores
  const validPattern = /^[a-zA-Z0-9_-]+$/;

  if (!validPattern.test(datasetId)) {
    return null;
  }

  // Limit length to prevent abuse
  if (datasetId.length > 100) {
    return null;
  }

  return datasetId;
}

/**
 * Sanitize transformation type to prevent injection
 * Only allows lowercase letters, numbers, and underscores
 *
 * @param type - The transformation type
 * @returns Validated type or null if invalid
 */
export function validateTransformationType(type: string): string | null {
  if (!type || typeof type !== 'string') {
    return null;
  }

  // Only allow lowercase letters, numbers, and underscores
  const validPattern = /^[a-z0-9_]+$/;

  if (!validPattern.test(type)) {
    return null;
  }

  // Limit length
  if (type.length > 50) {
    return null;
  }

  return type;
}
