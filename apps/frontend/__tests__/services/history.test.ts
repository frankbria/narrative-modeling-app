import { HistoryService } from '@/lib/services/history';
import { HistoryResponse, HistoryData } from '@/lib/types/history';

describe('HistoryService', () => {
  let service: HistoryService;
  const mockToken = 'test-token';
  const mockDatasetId = 'dataset-123';
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
        `${API_BASE}/api/v1/transformations/datasets/${mockDatasetId}/history/undo`,
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
        `${API_BASE}/api/v1/transformations/datasets/${mockDatasetId}/history/redo`,
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
        `${API_BASE}/api/v1/transformations/datasets/${mockDatasetId}/history/jump`,
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
    it('should fetch history data', async () => {
      const mockHistoryData: HistoryData = {
        history: [
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
        current_position: 1,
        can_undo: true,
        can_redo: false
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockHistoryData
      });

      const result = await service.getHistory(mockDatasetId, mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/v1/transformations/datasets/${mockDatasetId}/history`,
        {
          headers: {
            'Authorization': `Bearer ${mockToken}`
          }
        }
      );

      expect(result).toEqual(mockHistoryData);
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
        `${API_BASE}/api/v1/transformations/datasets/${mockDatasetId}/history`,
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
