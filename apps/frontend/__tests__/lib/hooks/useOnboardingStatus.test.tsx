import { renderHook, waitFor } from '@testing-library/react';
import { useOnboardingStatus } from '@/lib/hooks/useOnboardingStatus';

describe('useOnboardingStatus', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('reports incomplete onboarding from the status endpoint', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        is_onboarding_complete: false,
        current_step_id: 'upload_data',
      }),
    });

    const { result } = renderHook(() => useOnboardingStatus());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isComplete).toBe(false);
    expect(result.current.currentStepId).toBe('upload_data');
    expect(result.current.error).toBeNull();
  });

  it('reports complete onboarding', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        is_onboarding_complete: true,
        current_step_id: null,
      }),
    });

    const { result } = renderHook(() => useOnboardingStatus());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isComplete).toBe(true);
    expect(result.current.currentStepId).toBeNull();
  });

  it('calls the onboarding status endpoint with an auth header', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({ is_onboarding_complete: true }),
    });

    renderHook(() => useOnboardingStatus());

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain('/onboarding/status');
    expect(options.headers.Authorization).toBe('Bearer mock-token');
  });

  it('fails open (isComplete=true) when the request errors', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useOnboardingStatus());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isComplete).toBe(true);
    expect(result.current.error).not.toBeNull();
  });

  it('fails open when fetch rejects', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useOnboardingStatus());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isComplete).toBe(true);
    expect(result.current.error).toBe('network down');
  });
});
