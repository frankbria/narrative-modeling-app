import { useState, useEffect } from 'react';

/**
 * Hook that debounces a value for a specified delay
 * Useful for search inputs, form fields, and other frequently-changing values
 *
 * @param value - The value to debounce
 * @param delay - The debounce delay in milliseconds (default: 300)
 * @returns The debounced value
 *
 * @example
 * const [searchTerm, setSearchTerm] = useState('')
 * const debouncedSearchTerm = useDebounce(searchTerm, 300)
 *
 * useEffect(() => {
 *   // This effect only runs when debouncedSearchTerm changes
 *   // i.e., after 300ms of inactivity
 *   console.log('Search for:', debouncedSearchTerm)
 * }, [debouncedSearchTerm])
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
