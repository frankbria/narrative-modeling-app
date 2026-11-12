import { ApiError } from '@/lib/services/apiError';
import { notificationPreferencesApi } from '@/lib/services/notificationPreferences';

jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok') }));

const answer = (jobEmails: boolean) => ({ ok: true, json: async () => ({ job_emails: jobEmails }) });

describe('notificationPreferencesApi (#494)', () => {
  it('reads the preference from the version-prefixed route with the API token', async () => {
    global.fetch = jest.fn().mockResolvedValue(answer(true));

    await expect(notificationPreferencesApi.get()).resolves.toEqual({ job_emails: true });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/users\/me\/notification-preferences$/);
    expect(init.method).toBe('GET');
    expect(init.headers.Authorization).toBe('Bearer tok');
    expect(init.body).toBeUndefined();
  });

  it('saves a choice with PUT and answers what the server stored', async () => {
    global.fetch = jest.fn().mockResolvedValue(answer(false));

    await expect(notificationPreferencesApi.setJobEmails(false)).resolves.toEqual({ job_emails: false });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/users\/me\/notification-preferences$/);
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({ job_emails: false });
  });

  it('throws an ApiError carrying the status when the server refuses', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Database unavailable' }),
    });

    const refusal = await notificationPreferencesApi.get().catch((error: unknown) => error);

    expect(refusal).toBeInstanceOf(ApiError);
    expect((refusal as ApiError).status).toBe(503);
    expect((refusal as ApiError).message).toBe('Database unavailable');
  });
});
