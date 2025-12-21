/**
 * TypeScript interfaces for transformation history
 */

export interface HistoryEntry {
  position: number;
  timestamp: string;
  transformationType: string;
  description: string;
  affectedColumns: string[];
  rowsAffected?: number;
  versionId?: string;
}

export interface HistoryResponse {
  success: boolean;
  dataset_id: string;
  current_position: number;
  version_id: string;
  message: string;
}

export interface HistoryData {
  history: HistoryEntry[];
  current_position: number;
  can_undo: boolean;
  can_redo: boolean;
}

export interface HistoryState {
  currentPosition: number;
  entries: HistoryEntry[];
  lastSync: number;
}
