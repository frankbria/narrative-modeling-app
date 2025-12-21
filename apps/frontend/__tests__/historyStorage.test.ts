import {
  saveHistoryState,
  loadHistoryState,
  clearHistoryState
} from '@/lib/utils/historyStorage';
import { HistoryState } from '@/lib/types/history';

describe('historyStorage', () => {
  const mockDatasetId = 'dataset-123';
  const storageKey = `history_${mockDatasetId}`;

  let localStorageMock: Record<string, string>;
  let mockGetItem: jest.Mock;
  let mockSetItem: jest.Mock;
  let mockRemoveItem: jest.Mock;

  beforeEach(() => {
    localStorageMock = {};

    // Create jest mock functions that update the localStorageMock
    mockGetItem = jest.fn((key: string) => localStorageMock[key] || null);
    mockSetItem = jest.fn((key: string, value: string) => {
      localStorageMock[key] = value;
    });
    mockRemoveItem = jest.fn((key: string) => {
      delete localStorageMock[key];
    });

    // Replace global localStorage with mocked version
    Object.defineProperty(global, 'localStorage', {
      value: {
        getItem: mockGetItem,
        setItem: mockSetItem,
        removeItem: mockRemoveItem,
        clear: jest.fn(() => {
          localStorageMock = {};
        }),
        length: 0,
        key: jest.fn()
      },
      writable: true
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('saveHistoryState', () => {
    it('should save history state to localStorage', () => {
      const state: HistoryState = {
        currentPosition: 5,
        entries: [
          {
            position: 0,
            timestamp: '2024-01-01T00:00:00Z',
            transformationType: 'initial',
            description: 'Initial state',
            affectedColumns: []
          }
        ],
        lastSync: 0
      };

      saveHistoryState(mockDatasetId, state);

      expect(mockSetItem).toHaveBeenCalledWith(
        storageKey,
        expect.any(String)
      );

      const saved = JSON.parse(localStorageMock[storageKey]);
      expect(saved.currentPosition).toBe(5);
      expect(saved.entries).toHaveLength(1);
      expect(saved.lastSync).toBeGreaterThan(0);
    });

    it('should update lastSync timestamp when saving', () => {
      const state: HistoryState = {
        currentPosition: 3,
        entries: [],
        lastSync: 0
      };

      const beforeSave = Date.now();
      saveHistoryState(mockDatasetId, state);
      const afterSave = Date.now();

      const saved = JSON.parse(localStorageMock[storageKey]);
      expect(saved.lastSync).toBeGreaterThanOrEqual(beforeSave);
      expect(saved.lastSync).toBeLessThanOrEqual(afterSave);
    });

    it('should handle multiple dataset IDs independently', () => {
      const state1: HistoryState = {
        currentPosition: 1,
        entries: [],
        lastSync: 0
      };

      const state2: HistoryState = {
        currentPosition: 2,
        entries: [],
        lastSync: 0
      };

      saveHistoryState('dataset-1', state1);
      saveHistoryState('dataset-2', state2);

      const saved1 = JSON.parse(localStorageMock['history_dataset-1']);
      const saved2 = JSON.parse(localStorageMock['history_dataset-2']);

      expect(saved1.currentPosition).toBe(1);
      expect(saved2.currentPosition).toBe(2);
    });
  });

  describe('loadHistoryState', () => {
    it('should load history state from localStorage', () => {
      const state: HistoryState = {
        currentPosition: 3,
        entries: [
          {
            position: 0,
            timestamp: '2024-01-01T00:00:00Z',
            transformationType: 'initial',
            description: 'Initial state',
            affectedColumns: []
          }
        ],
        lastSync: Date.now()
      };

      localStorageMock[storageKey] = JSON.stringify(state);

      const loaded = loadHistoryState(mockDatasetId);

      expect(loaded).toEqual(state);
      expect(mockGetItem).toHaveBeenCalledWith(storageKey);
    });

    it('should return null if no data exists', () => {
      const loaded = loadHistoryState(mockDatasetId);

      expect(loaded).toBeNull();
      expect(mockGetItem).toHaveBeenCalledWith(storageKey);
    });

    it('should return null and clear if cache is expired', () => {
      const expiredState: HistoryState = {
        currentPosition: 2,
        entries: [],
        lastSync: Date.now() - (25 * 60 * 60 * 1000) // 25 hours ago
      };

      localStorageMock[storageKey] = JSON.stringify(expiredState);

      const loaded = loadHistoryState(mockDatasetId);

      expect(loaded).toBeNull();
      expect(mockRemoveItem).toHaveBeenCalledWith(storageKey);
    });

    it('should return null for malformed JSON', () => {
      localStorageMock[storageKey] = 'invalid json {';

      const loaded = loadHistoryState(mockDatasetId);

      expect(loaded).toBeNull();
    });

    it('should not expire cache within 24 hours', () => {
      const recentState: HistoryState = {
        currentPosition: 4,
        entries: [],
        lastSync: Date.now() - (23 * 60 * 60 * 1000) // 23 hours ago
      };

      localStorageMock[storageKey] = JSON.stringify(recentState);

      const loaded = loadHistoryState(mockDatasetId);

      expect(loaded).not.toBeNull();
      expect(loaded?.currentPosition).toBe(4);
    });
  });

  describe('clearHistoryState', () => {
    it('should remove history state from localStorage', () => {
      localStorageMock[storageKey] = JSON.stringify({
        currentPosition: 1,
        entries: [],
        lastSync: Date.now()
      });

      clearHistoryState(mockDatasetId);

      expect(mockRemoveItem).toHaveBeenCalledWith(storageKey);
      expect(localStorageMock[storageKey]).toBeUndefined();
    });

    it('should not throw error if key does not exist', () => {
      expect(() => {
        clearHistoryState('nonexistent-dataset');
      }).not.toThrow();

      expect(mockRemoveItem).toHaveBeenCalledWith('history_nonexistent-dataset');
    });

    it('should only clear the specified dataset', () => {
      localStorageMock['history_dataset-1'] = JSON.stringify({
        currentPosition: 1,
        entries: [],
        lastSync: Date.now()
      });

      localStorageMock['history_dataset-2'] = JSON.stringify({
        currentPosition: 2,
        entries: [],
        lastSync: Date.now()
      });

      clearHistoryState('dataset-1');

      expect(localStorageMock['history_dataset-1']).toBeUndefined();
      expect(localStorageMock['history_dataset-2']).toBeDefined();
    });
  });

  describe('integration', () => {
    it('should support save-load-clear cycle', () => {
      const state: HistoryState = {
        currentPosition: 7,
        entries: [
          {
            position: 0,
            timestamp: '2024-01-01T00:00:00Z',
            transformationType: 'initial',
            description: 'Initial state',
            affectedColumns: []
          },
          {
            position: 1,
            timestamp: '2024-01-01T01:00:00Z',
            transformationType: 'drop_column',
            description: 'Dropped column A',
            affectedColumns: ['A'],
            rowsAffected: 100
          }
        ],
        lastSync: 0
      };

      // Save
      saveHistoryState(mockDatasetId, state);
      expect(localStorageMock[storageKey]).toBeDefined();

      // Load
      const loaded = loadHistoryState(mockDatasetId);
      expect(loaded).not.toBeNull();
      expect(loaded?.currentPosition).toBe(7);
      expect(loaded?.entries).toHaveLength(2);

      // Clear
      clearHistoryState(mockDatasetId);
      expect(localStorageMock[storageKey]).toBeUndefined();

      // Load after clear
      const reloaded = loadHistoryState(mockDatasetId);
      expect(reloaded).toBeNull();
    });
  });
});
