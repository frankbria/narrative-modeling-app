import { API_URL } from '@/lib/constants'
import { getAuthToken } from '@/lib/auth-helpers'
import { apiError } from '@/lib/services/apiError'

export interface DatasetListItem {
  dataset_id: string
  filename: string
  num_rows: number
  num_columns: number
  created_at: string
}

/** The user's datasets, newest first (`GET /datasets`, the list the dashboard reads). */
export async function listDatasets(limit = 50): Promise<DatasetListItem[]> {
  const response = await fetch(`${API_URL}/datasets?page=1&limit=${limit}`, {
    headers: { Authorization: `Bearer ${await getAuthToken()}` },
  })
  if (!response.ok) throw await apiError(response, 'We could not load your datasets.')
  return (await response.json()).datasets ?? []
}
