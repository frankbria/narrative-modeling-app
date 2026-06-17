import { HistoryResponse, HistoryData, HistoryEntry } from '@/lib/types/history';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Raw shape of a history entry as emitted by the backend `HistoryDataResponse`
 * contract (snake_case). Mapped to the camelCase `HistoryEntry` before reaching
 * consumers — see {@link mapHistoryResponse}.
 */
interface RawHistoryEntry {
  position: number;
  timestamp: string;
  transformation_type: string;
  description: string;
  affected_columns?: string[];
  rows_affected?: number | null;
  version_id?: string | null;
}

interface RawHistoryData {
  history: RawHistoryEntry[];
  current_position: number;
  can_undo: boolean;
  can_redo: boolean;
}

/**
 * Convert a raw backend history payload (snake_case entry fields) into the
 * camelCase `HistoryData` shape the frontend types and components expect.
 *
 * The top-level fields (`current_position`, `can_undo`, `can_redo`) already
 * match the frontend contract; only each entry's fields are renamed.
 */
function mapHistoryResponse(raw: RawHistoryData): HistoryData {
  return {
    history: (raw.history ?? []).map(
      (entry): HistoryEntry => ({
        position: entry.position,
        timestamp: entry.timestamp,
        transformationType: entry.transformation_type,
        description: entry.description,
        affectedColumns: entry.affected_columns ?? [],
        rowsAffected: entry.rows_affected ?? undefined,
        versionId: entry.version_id ?? undefined,
      })
    ),
    current_position: raw.current_position,
    can_undo: raw.can_undo,
    can_redo: raw.can_redo,
  };
}

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

    const raw: RawHistoryData = await response.json();
    return mapHistoryResponse(raw);
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
