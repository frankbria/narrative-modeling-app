import React from 'react';

interface ButtonState {
  busy: boolean;
  success: boolean;
  large: boolean;
}

export function uploadButtonLabel(state: ButtonState): string {
  if (state.busy) return state.large ? 'Starting Chunked Upload...' : 'Scanning for PII...';
  if (state.success) return 'Uploaded';
  return state.large ? 'Start Chunked Upload' : 'Upload & Scan File';
}

export function uploadButtonColour(state: ButtonState): string {
  if (state.success) return 'bg-green-500 cursor-default';
  if (state.busy) return 'bg-blue-300 cursor-wait';
  return state.large ? 'bg-orange-500 hover:bg-orange-600' : 'bg-blue-500 hover:bg-blue-600';
}

export default function UploadButton(props: { show: boolean; state: ButtonState; onUpload: VoidFunction }) {
  const { show, state, onUpload } = props;
  if (!show) return null;
  return (
    <div className="mt-6 flex items-center justify-center">
      <button
        onClick={onUpload}
        disabled={state.busy || state.success}
        data-testid="upload-button"
        className={`px-6 py-3 rounded-md text-white font-semibold transition-all ${uploadButtonColour(state)}`}
      >
        {uploadButtonLabel(state)}
      </button>
    </div>
  );
}
