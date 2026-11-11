/**
 * Whether the account is emailed when a training or batch prediction job ends (#494).
 * The backend half is `app/api/routes/users.py`; an account that never chose is on.
 */
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { apiError } from '@/lib/services/apiError';

export interface NotificationPreferences {
  job_emails: boolean;
}

/** The PUT body, pinned to the backend's request model by `notificationPreferences.contract.test.ts`. */
export const jobEmailsBody = (enabled: boolean): NotificationPreferences => ({ job_emails: enabled });

async function request(method: 'GET' | 'PUT', body?: NotificationPreferences): Promise<NotificationPreferences> {
  const token = await getAuthToken();
  const response = await fetch(`${API_URL}/users/me/notification-preferences`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body && JSON.stringify(body),
  });
  if (!response.ok) {
    throw await apiError(response, 'Notification preferences are unavailable');
  }
  return (await response.json()) as NotificationPreferences;
}

export const notificationPreferencesApi = {
  get: () => request('GET'),
  setJobEmails: (enabled: boolean) => request('PUT', jobEmailsBody(enabled)),
};
