/**
 * Onboarding API client (#470).
 *
 * Every call builds its URL from `NEXT_PUBLIC_API_URL` — which already carries the
 * `/api/v1` prefix — plus the resource path, and sends the minted API JWT. The
 * onboarding page and the sample-dataset selector used to `fetch('/api/v1/…')`:
 * relative to the *frontend* origin, unauthenticated, a 404 on every first-time
 * user's first screen. A non-2xx response is thrown, never silently parsed.
 */
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';

export class OnboardingApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = 'OnboardingApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAuthToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new OnboardingApiError(response.status, `Onboarding request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export const onboardingApi = {
  getStatus: <T = unknown>() => request<T>('/onboarding/status'),
  getSteps: <T = unknown>() => request<T>('/onboarding/steps'),
  getAchievements: <T = unknown>() => request<T>('/onboarding/achievements'),
  completeStep: <T = unknown>(stepId: string, completionData: Record<string, unknown> = {}) =>
    request<T>(`/onboarding/steps/${stepId}/complete`, {
      method: 'POST',
      body: JSON.stringify({ completion_data: completionData }),
    }),
  skipStep: <T = unknown>(stepId: string) =>
    request<T>(`/onboarding/skip-step/${stepId}`, { method: 'POST' }),
  getSampleDatasets: <T = unknown>() => request<T>('/onboarding/sample-datasets'),
  loadSampleDataset: <T = unknown>(datasetId: string) =>
    request<T>(`/onboarding/sample-datasets/${datasetId}/load`, { method: 'POST' }),
};
