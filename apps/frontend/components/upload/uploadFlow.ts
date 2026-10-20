import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { apiError } from '@/lib/services/apiError';
import type { PIIReport } from '@/lib/types/api';
import { CHUNKED_UPLOAD_MB } from '@/lib/trust/datasetFacts';

/** Files above this size go through the chunked upload. */
export const CHUNKED_UPLOAD_THRESHOLD = CHUNKED_UPLOAD_MB * 1024 * 1024;

export type PreviewCell = string | number | boolean | null;

/** What the three upload routes answer: `/upload/secure`, `/confirm-pii-upload`, chunked `complete`. */
export interface UploadAnswer {
  status?: string;
  file_id?: string;
  filename?: string;
  preview?: Record<string, unknown>[];
  pii_report?: PIIReport;
  requires_confirmation?: boolean;
}

export interface PreviewData {
  headers: string[];
  previewData: PreviewCell[][];
  fileName: string;
  fileType: string;
  id?: string;
  pii_report?: PIIReport;
  status?: string;
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/** The lower-cased text after the last dot, or the whole name when it has none. */
export function extensionOf(name: string): string {
  return name.slice(name.lastIndexOf('.') + 1).toLowerCase();
}

export function nameOf(file: File | null): string {
  return file?.name || '';
}

/** The first ten preview rows of an upload's answer, as the table renders them. */
export function toPreviewData(answer: UploadAnswer, fileName: string, id: string): PreviewData {
  const rows = answer.preview || [];
  return {
    headers: Object.keys(rows[0] || {}),
    previewData: rows.slice(0, 10).map((row) => Object.values(row) as PreviewCell[]),
    fileName: answer.filename || fileName,
    fileType: extensionOf(fileName),
    id,
    pii_report: answer.pii_report,
    status: answer.status,
  };
}

export function messageOf(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

/** POST a multipart form to an upload route with the API token. */
export async function postForm(path: string, form: FormData): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    method: 'POST',
    body: form,
    headers: {
      'Authorization': `Bearer ${await getAuthToken()}`
    }
  });
}

/** The answer's body, or the backend's error (status and detail kept, #767). */
export async function readAnswer(response: Response, fallback: string): Promise<UploadAnswer> {
  if (!response.ok) {
    throw await apiError(response, fallback);
  }
  return response.json();
}
