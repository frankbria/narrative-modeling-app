import { HistoryService } from '@/lib/services/history';
import { HistoryResponse, HistoryData } from '@/lib/types/history';

describe('HistoryService', () => {
  let service: HistoryService;
  const mockToken = 'test-token';
  const mockDatasetId = 'dataset-123';
  // This suite covers request/response behaviour, NOT URL correctness — it cannot.
  // With NEXT_PUBLIC_API_URL unset (as in CI) the pre-#406 service produced
  // 'http://localhost:8000' + '/api/v1/transformations/...' and the fixed one
  // produces 'http://localhost:8000/api/v1' + '/transformations/...' — byte-identical.
  // The doubled prefix only appears once the env var is actually set, which is why
  // it shipped and why asserting it here is impossible.
  // `__tests__/lib/apiUrlConstruction.test.ts` owns that: it sets the env var
  // explicitly and pins every path against the real FastAPI route table.
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  beforeEach(() => {
    service = new HistoryService();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('undo', () => {
    it('should call undo endpoint correctly', async () => {
      const mockResponse: HistoryResponse = {
        success: true,
        dataset_id: mockDatasetId,
        current_position: 5,
        version_id: 'version-123',
        message: 'Undone successfully'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await service.undo(mockDatasetId, mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE}/transformations/datasets/${mockDatasetId}/history/undo`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${mockToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      expect(result).toEqual(mockResponse);
    });

    it('should throw error when undo fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Bad Request'
      });

      await expect(service.undo(mockDatasetId, mockToken))
        .rejects.toThrow('Undo failed: Bad Request');
    });
  });

  describe('redo', () => {
    it('should call redo endpoint correctly', async () => {
      const mockResponse: HistoryResponse = {
        success: true,
        dataset_id: mockDatasetId,
        current_position: 7,
        version_id: 'version-456',
        message: 'Redone successfully'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await service.redo(mockDatasetId, mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE}/transformations/datasets/${mockDatasetId}/history/redo`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${mockToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      expect(result).toEqual(mockResponse);
    });

    it('should throw error when redo fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Conflict'
      });

      await expect(service.redo(mockDatasetId, mockToken))
        .rejects.toThrow('Redo failed: Conflict');
    });
  });

  describe('jumpToPosition', () => {
    it('should call jump endpoint with position', async () => {
      const targetPosition = 3;
      const mockResponse: HistoryResponse = {
        success: true,
        dataset_id: mockDatasetId,
        current_position: targetPosition,
        version_id: 'version-789',
        message: 'Jumped to position 3'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await service.jumpToPosition(mockDatasetId, targetPosition, mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE}/transformations/datasets/${mockDatasetId}/history/jump`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${mockToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ position: targetPosition })
        }
      );

      expect(result).toEqual(mockResponse);
    });

    it('should throw error when jump fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Not Found'
      });

      await expect(service.jumpToPosition(mockDatasetId, 5, mockToken))
        .rejects.toThrow('Jump failed: Not Found');
    });
  });

  describe('getHistory', () => {
    it('should fetch history data and map snake_case API fields to camelCase', async () => {
      // Mirrors the actual backend HistoryDataResponse contract: top-level fields
      // are already snake_case, but each entry uses snake_case keys
      // (transformation_type / affected_columns / rows_affected / version_id).
      const mockApiResponse = {
        history: [
          {
            position: 0,
            timestamp: '2024-01-01T00:00:00Z',
            transformation_type: 'initial',
            description: 'Initial state',
            affected_columns: [],
            rows_affected: null,
            version_id: null
          },
          {
            position: 1,
            timestamp: '2024-01-01T01:00:00Z',
            transformation_type: 'drop_column',
            description: 'Dropped column A',
            affected_columns: ['A'],
            rows_affected: 100,
            version_id: 'version-abc'
          }
        ],
        current_position: 1,
        can_undo: true,
        can_redo: false
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockApiResponse
      });

      const result = await service.getHistory(mockDatasetId, mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE}/transformations/datasets/${mockDatasetId}/history`,
        {
          headers: {
            'Authorization': `Bearer ${mockToken}`
          }
        }
      );

      const expected: HistoryData = {
        history: [
          {
            position: 0,
            timestamp: '2024-01-01T00:00:00Z',
            transformationType: 'initial',
            description: 'Initial state',
            affectedColumns: [],
            rowsAffected: undefined,
            versionId: undefined
          },
          {
            position: 1,
            timestamp: '2024-01-01T01:00:00Z',
            transformationType: 'drop_column',
            description: 'Dropped column A',
            affectedColumns: ['A'],
            rowsAffected: 100,
            versionId: 'version-abc'
          }
        ],
        current_position: 1,
        can_undo: true,
        can_redo: false
      };

      expect(result).toEqual(expected);
      // Ensure no snake_case entry keys leak through to consumers.
      expect(result.history[1]).not.toHaveProperty('transformation_type');
      expect(result.history[1]).not.toHaveProperty('affected_columns');
      expect(result.history[1]).not.toHaveProperty('rows_affected');
      expect(result.history[1]).not.toHaveProperty('version_id');
    });

    it('should default affected_columns to an empty array when omitted', async () => {
      const mockApiResponse = {
        history: [
          {
            position: 0,
            timestamp: '2024-01-01T00:00:00Z',
            transformation_type: 'initial',
            description: 'Initial state'
          }
        ],
        current_position: 0,
        can_undo: false,
        can_redo: false
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockApiResponse
      });

      const result = await service.getHistory(mockDatasetId, mockToken);

      expect(result.history[0].affectedColumns).toEqual([]);
      expect(result.history[0].rowsAffected).toBeUndefined();
      expect(result.history[0].versionId).toBeUndefined();
    });

    it('should throw error when get history fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Internal Server Error'
      });

      await expect(service.getHistory(mockDatasetId, mockToken))
        .rejects.toThrow('Get history failed: Internal Server Error');
    });
  });

  describe('clearHistory', () => {
    it('should call clear history endpoint', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true
      });

      await service.clearHistory(mockDatasetId, mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE}/transformations/datasets/${mockDatasetId}/history`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${mockToken}`
          }
        }
      );
    });

    it('should throw error when clear history fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Forbidden'
      });

      await expect(service.clearHistory(mockDatasetId, mockToken))
        .rejects.toThrow('Clear history failed: Forbidden');
    });
  });

  describe('API errors', () => {
    it('should handle network errors gracefully', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      );

      await expect(service.undo(mockDatasetId, mockToken))
        .rejects.toThrow('Network error');
    });

    it('should handle malformed JSON responses', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        }
      });

      await expect(service.getHistory(mockDatasetId, mockToken))
        .rejects.toThrow('Invalid JSON');
    });
  });
});
