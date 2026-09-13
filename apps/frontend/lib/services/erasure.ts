/**
 * Right-to-erasure API client (#482). Backs the settings "delete my account and
 * data" action and the per-dataset erase action. The backend cascade lives in
 * DatasetErasureService (#259/#497/#480); this just calls it and returns the
 * manifest so the UI can surface exactly what was removed and refuse to claim
 * success on a partial failure.
 *
 * Every call builds its URL from `API_URL` (which already carries `/api/v1`) and
 * sends the minted API JWT; a non-2xx response throws.
 */
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import type { EraseResponse } from '@/lib/types/erasure';

export class ErasureApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ErasureApiError';
  }
}

async function post(path: string): Promise<EraseResponse> {
  const token = await getAuthToken();
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    // The backend body (ErasureRequest.reason) is optional; omit it.
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new ErasureApiError(response.status, `Erasure request failed (${response.status})`);
  }
  return (await response.json()) as EraseResponse;
}

export const erasureApi = {
  /** Erase all data owned by the current user (keeps the account/auth record). */
  eraseCurrentUser: () => post('/users/me/erase'),
  /** Erase a single dataset and its cascade (both id-spaces). */
  eraseDataset: (datasetId: string) =>
    post(`/datasets/${encodeURIComponent(datasetId)}/erase`),
};
