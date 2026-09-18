/**
 * Operator readouts (#769 AC2). The backend answers 404 to anyone not on
 * ADMIN_EMAILS, matching the /admin page's own guard.
 */
import { API_BASE_URL } from '@/lib/config'
import { getAuthToken } from '@/lib/auth-helpers'
import { apiError } from '@/lib/services/apiError'

/** Mirrors `app/services/product_events.py::funnel`. */
export interface Funnel {
  days: number
  signups: number
  signups_per_day: { date: string; count: number }[]
  activation: { cohort: number; activated: number; rate: number | null }
  quota_denials_by_metric: Record<string, number>
  checkout_started: number
  checkout_completed: number
  subscriptions_cancelled: number
}

export async function getFunnel(days = 30): Promise<Funnel> {
  const token = await getAuthToken()
  const response = await fetch(`${API_BASE_URL}/admin/funnel?days=${days}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw await apiError(response, 'Could not load the funnel')
  return response.json()
}
