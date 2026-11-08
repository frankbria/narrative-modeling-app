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
  if (state.success) return 'bg-success text-success-foreground cursor-default';
  if (state.busy) return 'bg-muted text-muted-foreground cursor-wait';
  return state.large ? 'bg-warning text-warning-foreground hover:bg-warning/90' : 'bg-primary text-primary-foreground hover:bg-primary/90';
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
        className={`px-6 py-3 rounded-md font-semibold transition-all ${uploadButtonColour(state)}`}
      >
        {uploadButtonLabel(state)}
      </button>
    </div>
  );
}
