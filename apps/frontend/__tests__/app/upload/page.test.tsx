/**
 * The upload page, rendered (#778). Every dataset enters through it, and its two
 * requests' failure paths were covered only end to end: a regression in how a
 * plan-limit refusal or a backend error reaches the user showed in the e2e smoke
 * job and nowhere in jest.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import UploadPage from '@/app/upload/page';
import { API_URL } from '@/lib/constants';
import { planLimit } from '@/lib/billing/planLimit';
import { QuotaExceededError } from '@/lib/services/apiError';

const completeStage = jest.fn();
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({ completeStage, resetWorkflow: jest.fn(), state: { datasetId: null } }),
}));
jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok-123') }));
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'user-123' } }, status: 'authenticated' }),
}));

const QUOTA_SENTENCE = 'You have used all 20 uploads included in the free plan this month.';
const QUOTA_DETAIL = {
  error: 'quota_exceeded',
  metric: 'uploads',
  limit: 20,
  used: 20,
  tier: 'free',
  resets_at: '2026-11-01T00:00:00+00:00',
  message: QUOTA_SENTENCE,
  upgrade_available: true,
};
const PII_REPORT = {
  has_pii: true,
  total_detections: 3,
  risk_level: 'high',
  affected_columns: ['ssn'],
  detections: [{ column: 'ssn', type: 'ssn', confidence: 0.95 }],
};
const STORED = {
  status: 'success',
  file_id: '6ace00000000000000000001',
  filename: 'staff.csv',
  preview: [{ name: 'Ada', ssn: '***-**-1234' }],
};

type Answer = { status: number; body: unknown };
const ok = (body: unknown): Answer => ({ status: 200, body });
const refused = (status: number, body: unknown = {}): Answer => ({ status, body });

/** `fetch` answering each path with what the backend would, and recording what it was sent. */
function backend(answers: Record<string, Answer>) {
  const calls: Array<{ path: string; init: RequestInit }> = [];
  global.fetch = jest.fn(async (url: string, init: RequestInit) => {
    const path = String(url).replace(API_URL, '');
    calls.push({ path, init });
    const answer = answers[path];
    if (!answer) throw new Error(`unexpected request to ${path}`);
    return {
      ok: answer.status < 400,
      status: answer.status,
      statusText: '',
      json: async () => answer.body,
      text: async () => JSON.stringify(answer.body),
    };
  }) as unknown as typeof fetch;
  return calls;
}

/** Choose a small CSV the way a user does and press Upload. */
async function uploadCsv() {
  render(<UploadPage />);
  const csv = new File(['name,ssn\nAda,123-45-6789\n'], 'staff.csv', { type: 'text/csv' });
  fireEvent.change(screen.getByTestId('file-input'), { target: { files: [csv] } });
  const button = await screen.findByTestId('upload-button');
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
}

const errorMessage = () => screen.findByTestId('upload-error-message');

beforeEach(() => {
  jest.clearAllMocks();
  planLimit.dismiss();
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

describe('UploadPage: POST /upload/secure', () => {
  it('stores the file, completes the stage and offers the way to the dataset', async () => {
    const calls = backend({ '/upload/secure': ok(STORED) });

    await uploadCsv();

    expect(await screen.findByTestId('file-id')).toHaveTextContent(STORED.file_id);
    expect(completeStage).toHaveBeenCalledWith(
      'data_loading',
      expect.objectContaining({ datasetId: STORED.file_id, filename: 'staff.csv' }),
    );
    const [{ init }] = calls;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
    expect(((init.body as FormData).get('file') as File).name).toBe('staff.csv');

    fireEvent.click(screen.getByTestId('next-step-button'));
    const { push } = (global as unknown as { __NEXT_ROUTER_MOCKS__: { push: jest.Mock } }).__NEXT_ROUTER_MOCKS__;
    expect(push).toHaveBeenCalledWith(`/explore/${STORED.file_id}`);
  });

  it('a plan-limit refusal opens the plan-limit dialog and shows the backend sentence', async () => {
    backend({ '/upload/secure': refused(402, { detail: QUOTA_DETAIL }) });

    await uploadCsv();

    expect(await errorMessage()).toHaveTextContent(QUOTA_SENTENCE);
    const shown = planLimit.get();
    expect(shown).toBeInstanceOf(QuotaExceededError);
    expect(shown).toMatchObject({ metric: 'uploads', limit: 20, used: 20, tier: 'free' });
    expect(completeStage).not.toHaveBeenCalled();
  });

  it('any other refusal shows what the backend said, and opens no dialog', async () => {
    backend({ '/upload/secure': refused(400, { detail: 'The file has no rows.' }) });

    await uploadCsv();

    expect(await errorMessage()).toHaveTextContent('The file has no rows.');
    expect(planLimit.get()).toBeNull();
  });

  it('a failure with nothing to say falls back to the status', async () => {
    backend({ '/upload/secure': refused(502) });

    await uploadCsv();

    expect(await errorMessage()).toHaveTextContent('Upload failed: 502');
    expect(planLimit.get()).toBeNull();
  });

  it('a 200 that is neither stored nor a PII warning is an error, not a silent success', async () => {
    backend({ '/upload/secure': ok({ status: 'queued' }) });

    await uploadCsv();

    expect(await errorMessage()).toHaveTextContent('Unexpected response format');
    expect(completeStage).not.toHaveBeenCalled();
  });
});

describe('UploadPage: POST /upload/confirm-pii-upload', () => {
  const WARNED = ok({ status: 'pii_detected', requires_confirmation: true, pii_report: PII_REPORT });

  async function reachTheWarning(confirm: Answer) {
    const calls = backend({ '/upload/secure': WARNED, '/upload/confirm-pii-upload': confirm });
    await uploadCsv();
    expect(await screen.findByText('Sensitive Data Detected')).toBeInTheDocument();
    return calls;
  }

  const confirmWith = (label: RegExp) => fireEvent.click(screen.getByRole('button', { name: label }));
  const maskFlag = (calls: Array<{ path: string; init: RequestInit }>) =>
    (calls.find((c) => c.path === '/upload/confirm-pii-upload')!.init.body as FormData).get('mask_pii');

  it('nothing is stored until the user chooses, and masking is sent as chosen', async () => {
    const masked = await reachTheWarning(ok(STORED));
    expect(completeStage).not.toHaveBeenCalled();

    confirmWith(/upload with data masking/i);

    expect(await screen.findByTestId('file-id')).toHaveTextContent(STORED.file_id);
    expect(maskFlag(masked)).toBe('true');
    expect(screen.queryByText('Sensitive Data Detected')).not.toBeInTheDocument();
    expect(completeStage).toHaveBeenCalledWith('data_loading', expect.objectContaining({ datasetId: STORED.file_id }));
  });

  it('uploading without masking says so to the backend', async () => {
    const unmasked = await reachTheWarning(ok(STORED));

    confirmWith(/upload original data/i);

    expect(await screen.findByTestId('file-id')).toBeInTheDocument();
    expect(maskFlag(unmasked)).toBe('false');
  });

  it('cancelling stores nothing and puts the warning away', async () => {
    const calls = await reachTheWarning(ok(STORED));

    confirmWith(/cancel upload/i);

    expect(screen.queryByText('Sensitive Data Detected')).not.toBeInTheDocument();
    expect(calls.map((c) => c.path)).toEqual(['/upload/secure']);
    expect(completeStage).not.toHaveBeenCalled();
  });

  it('a plan-limit refusal opens the plan-limit dialog and shows the backend sentence', async () => {
    await reachTheWarning(refused(402, { detail: QUOTA_DETAIL }));

    confirmWith(/upload with data masking/i);

    expect(await errorMessage()).toHaveTextContent(QUOTA_SENTENCE);
    expect(planLimit.get()).toMatchObject({ metric: 'uploads', limit: 20 });
    expect(completeStage).not.toHaveBeenCalled();
  });

  it('any other refusal shows what the backend said, or the fallback, and opens no dialog', async () => {
    await reachTheWarning(refused(400, { detail: 'The file changed since it was scanned.' }));
    confirmWith(/upload with data masking/i);
    expect(await errorMessage()).toHaveTextContent('The file changed since it was scanned.');
    expect(planLimit.get()).toBeNull();
  });

  it('a failure with nothing to say falls back to its own sentence', async () => {
    await reachTheWarning(refused(502));
    confirmWith(/upload with data masking/i);
    expect(await errorMessage()).toHaveTextContent('Failed to upload with PII');
    expect(planLimit.get()).toBeNull();
  });
});
