import { HistoryResponse, HistoryData } from '@/lib/types/history';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Service for managing transformation history operations
 */
export class HistoryService {
  /**
   * Undo the last transformation
   */
  async undo(datasetId: string, token: string): Promise<HistoryResponse> {
    const response = await fetch(
      `${API_BASE}/api/v1/transformations/datasets/${datasetId}/history/undo`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Undo failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Redo the next transformation
   */
  async redo(datasetId: string, token: string): Promise<HistoryResponse> {
    const response = await fetch(
      `${API_BASE}/api/v1/transformations/datasets/${datasetId}/history/redo`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Redo failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Jump to a specific position in history
   */
  async jumpToPosition(
    datasetId: string,
    position: number,
    token: string
  ): Promise<HistoryResponse> {
    const response = await fetch(
      `${API_BASE}/api/v1/transformations/datasets/${datasetId}/history/jump`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ position })
      }
    );

    if (!response.ok) {
      throw new Error(`Jump failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get the full transformation history
   */
  async getHistory(datasetId: string, token: string): Promise<HistoryData> {
    const response = await fetch(
      `${API_BASE}/api/v1/transformations/datasets/${datasetId}/history`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Get history failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Clear all transformation history
   */
  async clearHistory(datasetId: string, token: string): Promise<void> {
    const response = await fetch(
      `${API_BASE}/api/v1/transformations/datasets/${datasetId}/history`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Clear history failed: ${response.statusText}`);
    }
  }
}
