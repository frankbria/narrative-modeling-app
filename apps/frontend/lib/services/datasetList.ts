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

/** One `GET /user_data/` row (`UserDataResponse`). */
interface UserDataRow {
  _id: string
  original_filename: string
  num_rows: number
  num_columns: number
  created_at: string
}

/**
 * The user's uploads, newest first. `GET /user_data/`, not `/datasets`: an upload is a
 * UserData document, its id is the one every stage page opens, and `/datasets` (the
 * DatasetMetadata list) never shows it (#1167).
 */
export async function listDatasets(): Promise<DatasetListItem[]> {
  const response = await fetch(`${API_URL}/user_data/`, {
    headers: { Authorization: `Bearer ${await getAuthToken()}` },
  })
  if (!response.ok) throw await apiError(response, 'We could not load your datasets.')
  const rows: UserDataRow[] = await response.json()
  return rows
    .map((row) => ({
      dataset_id: row._id,
      filename: row.original_filename,
      num_rows: row.num_rows,
      num_columns: row.num_columns,
      created_at: row.created_at,
    }))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
}
