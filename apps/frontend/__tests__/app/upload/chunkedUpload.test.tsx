/**
 * The upload page's large-file path: a file over the 50MB threshold goes through the
 * chunked upload hook, whose own requests have their own suite. This drives the page's
 * side of it, with the hook replaced by one that reports what the page hands it.
 */
import React from 'react';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import UploadPage from '@/app/upload/page';
import type { ChunkedPiiPause, ChunkedUploadResponse } from '@/lib/types/api';

const completeStage = jest.fn();
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({ completeStage, resetWorkflow: jest.fn(), state: { datasetId: null } }),
}));

interface Options {
  onComplete(fileId: string, response: ChunkedUploadResponse): void;
  onPiiDetected(pause: ChunkedPiiPause): void;
  onError(error: string): void;
}
const hook = {
  options: null as Options | null,
  uploadFile: jest.fn(),
  confirmUpload: jest.fn(),
  cancelUpload: jest.fn(),
  progress: null as unknown,
};
jest.mock('@/lib/hooks/useChunkedUpload', () => ({
  __esModule: true,
  default: (options: Options) => {
    hook.options = options;
    return {
      uploadFile: hook.uploadFile,
      confirmUpload: hook.confirmUpload,
      uploadState: hook.progress,
      isUploading: false,
      cancelUpload: hook.cancelUpload,
      resetUpload: jest.fn(),
    };
  },
}));

const PROGRESS = {
  sessionId: 's1', totalChunks: 12, uploadedChunks: 3, currentChunk: 3, progress: 25,
  bytesUploaded: 15 * 1024 * 1024, totalBytes: 60 * 1024 * 1024, speed: 1024 * 1024,
  remainingTime: 45, status: 'uploading',
};

async function chooseLargeFile() {
  render(<UploadPage />);
  const big = new File(['name\nAda\n'], 'big.csv', { type: 'text/csv' });
  Object.defineProperty(big, 'size', { value: 60 * 1024 * 1024 });
  fireEvent.change(screen.getByTestId('file-input'), { target: { files: [big] } });
  const button = await screen.findByTestId('upload-button');
  return { big, button };
}

beforeEach(() => {
  jest.clearAllMocks();
  hook.progress = null;
  hook.uploadFile.mockResolvedValue(undefined);
  hook.confirmUpload.mockResolvedValue(undefined);
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

it('a large file is announced and sent through the chunked upload', async () => {
  const { big, button } = await chooseLargeFile();

  expect(button).toHaveTextContent('Start Chunked Upload');
  expect(screen.getByText('Large File Detected')).toBeInTheDocument();
  expect(screen.getByText('Large File - Chunked Upload')).toBeInTheDocument();
  expect(screen.getByText(/Your file is 60 MB, which exceeds our 50 MB threshold/)).toBeInTheDocument();

  fireEvent.click(button);
  await waitFor(() => expect(hook.uploadFile).toHaveBeenCalledWith(big));
  expect(screen.queryByTestId('upload-button')).not.toBeInTheDocument();
});

it('a completed chunked upload shows its preview and completes the stage', async () => {
  const { button } = await chooseLargeFile();
  fireEvent.click(button);

  act(() =>
    hook.options!.onComplete('file-9', {
      file_id: 'file-9',
      filename: 'big.csv',
      status: 'success',
      preview: [{ name: 'Ada' }],
      pii_report: { has_pii: false, risk_level: 'low', summary: '', recommendations: [] },
    }),
  );

  expect(await screen.findByTestId('file-id')).toHaveTextContent('file-9');
  expect(screen.getByText('NO PII DETECTED')).toBeInTheDocument();
  expect(screen.getByText('Ada')).toBeInTheDocument();
  expect(completeStage).toHaveBeenCalledWith('data_loading', expect.objectContaining({ datasetId: 'file-9', filename: 'big.csv' }));
});

it('a failed chunked upload shows the error, and a throw from the hook is not unhandled', async () => {
  hook.uploadFile.mockRejectedValue(new Error('chunk 3 failed'));
  const { button } = await chooseLargeFile();
  fireEvent.click(button);

  act(() => hook.options!.onError('chunk 3 failed'));

  expect(await screen.findByTestId('upload-error-message')).toHaveTextContent('chunk 3 failed');
});

it('the progress panel cancels the upload and forgets the file', async () => {
  hook.progress = PROGRESS;
  const { button } = await chooseLargeFile();
  fireEvent.click(button);

  fireEvent.click(await screen.findByRole('button', { name: /cancel/i }));

  expect(hook.cancelUpload).toHaveBeenCalled();
  expect(screen.getByText(/Drag a .csv/)).toBeInTheDocument();
});

describe('a high-risk chunked upload (#1122)', () => {
  const PAUSE: ChunkedPiiPause = {
    status: 'pii_detected',
    requires_confirmation: true,
    session_id: 's-held',
    pii_report: {
      has_pii: true, risk_level: 'high', summary: '', recommendations: [],
      total_pii_columns: 1, high_risk_columns: 1,
      detections: [{ column: 'ssn', type: 'ssn', confidence: 0.95, recommendation: '' }],
    },
  };

  async function pausedUpload() {
    const { button } = await chooseLargeFile();
    fireEvent.click(button);
    act(() => hook.options!.onPiiDetected(PAUSE));
    await screen.findByText('Sensitive Data Detected');
  }

  it('shows the PII warning and stores nothing', async () => {
    await pausedUpload();

    expect(completeStage).not.toHaveBeenCalled();
    expect(screen.queryByTestId('file-id')).not.toBeInTheDocument();
  });

  it.each([
    ['Upload with Data Masking', true],
    ['Upload Original Data', false],
  ])('%s confirms the held upload with the user\'s choice', async (label, mask) => {
    await pausedUpload();

    fireEvent.click(screen.getByRole('button', { name: label }));

    await waitFor(() => expect(hook.confirmUpload).toHaveBeenCalledWith('s-held', mask));
    await waitFor(() => expect(screen.queryByText('Sensitive Data Detected')).not.toBeInTheDocument());
  });

  it('cancelling discards the held upload and forgets the file', async () => {
    await pausedUpload();

    fireEvent.click(screen.getByRole('button', { name: 'Cancel Upload' }));

    expect(hook.cancelUpload).toHaveBeenCalled();
    expect(hook.confirmUpload).not.toHaveBeenCalled();
    expect(screen.getByText(/Drag a .csv/)).toBeInTheDocument();
  });

  it('a refused confirmation keeps the choice on screen and shows the error', async () => {
    hook.confirmUpload.mockRejectedValue(new Error('Upload session not found'));
    await pausedUpload();

    fireEvent.click(screen.getByRole('button', { name: 'Upload Original Data' }));
    act(() => hook.options!.onError('Upload session not found'));

    expect(await screen.findByTestId('upload-error-message')).toHaveTextContent('Upload session not found');
  });
});
