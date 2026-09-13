import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '@/app/settings/page';
import { erasureApi } from '@/lib/services/erasure';
import type { EraseResponse } from '@/lib/types/erasure';

const ROUTER = (global as unknown as { __NEXT_ROUTER_MOCKS__: { push: jest.Mock } }).__NEXT_ROUTER_MOCKS__;

jest.mock('@/lib/services/erasure', () => ({
  erasureApi: { eraseCurrentUser: jest.fn(), eraseDataset: jest.fn() },
}));

const cleanResponse: EraseResponse = {
  erasure_id: 'e1',
  status: 'completed',
  manifest: {
    target_type: 'user',
    target_id: 'u1',
    subject_user_id: 'u1',
    erasure_id: 'e1',
    documents_deleted: { datasets: 2 },
    s3_objects_deleted: [],
    redis_keys_evicted: 0,
    failures: [],
    notes: ['retained Subscription/UsageRecord'],
    idempotent_noop: false,
    completed_at: '2026-09-12T00:00:00Z',
    total_documents_deleted: 2,
    status: 'completed',
  },
};

describe('SettingsPage account erasure wiring (#482)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    ROUTER.push.mockClear();
  });

  it('shows the success summary first and navigates only on Close (AC5)', async () => {
    (erasureApi.eraseCurrentUser as jest.Mock).mockResolvedValue(cleanResponse);
    render(<SettingsPage />);

    fireEvent.click(screen.getByTestId('delete-account'));
    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByTestId('confirm-erasure'));

    // The manifest summary is visible AND we have NOT navigated away yet.
    await waitFor(() => expect(screen.getByText(/Removed 2 records/i)).toBeInTheDocument());
    expect(ROUTER.push).not.toHaveBeenCalled();

    // Closing after a clean erase navigates to the dashboard.
    fireEvent.click(screen.getByTestId('erasure-close'));
    expect(ROUTER.push).toHaveBeenCalledWith('/dashboard');
  });

  it('does not navigate when the dialog is cancelled without erasing', () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByTestId('delete-account'));
    fireEvent.click(screen.getByText('Cancel'));
    expect(ROUTER.push).not.toHaveBeenCalled();
    expect(erasureApi.eraseCurrentUser).not.toHaveBeenCalled();
  });
});
