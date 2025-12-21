import { HistoryState } from '@/lib/types/history';

const STORAGE_PREFIX = 'history_';
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Save history state to localStorage with timestamp
 */
export function saveHistoryState(datasetId: string, state: HistoryState): void {
  const key = `${STORAGE_PREFIX}${datasetId}`;
  const data = {
    ...state,
    lastSync: Date.now()
  };
  localStorage.setItem(key, JSON.stringify(data));
}

/**
 * Load history state from localStorage
 * Returns null if not found or expired
 */
export function loadHistoryState(datasetId: string): HistoryState | null {
  const key = `${STORAGE_PREFIX}${datasetId}`;
  const stored = localStorage.getItem(key);

  if (!stored) return null;

  try {
    const data = JSON.parse(stored);

    // Check if cache is expired
    if (Date.now() - data.lastSync > CACHE_EXPIRY_MS) {
      clearHistoryState(datasetId);
      return null;
    }

    return data;
  } catch {
    return null;
  }
}

/**
 * Clear history state from localStorage
 */
export function clearHistoryState(datasetId: string): void {
  const key = `${STORAGE_PREFIX}${datasetId}`;
  localStorage.removeItem(key);
}
