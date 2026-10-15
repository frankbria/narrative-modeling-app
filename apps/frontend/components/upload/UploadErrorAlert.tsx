import React from 'react';
import { AlertCircle } from 'lucide-react';

export default function UploadErrorAlert(props: { message: string | null }) {
  const { message } = props;
  if (!message) return null;
  return (
    <div className="mt-4 p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-md" data-testid="upload-error" role="alert" aria-live="assertive">
      <div className="flex items-start gap-2">
        <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
        <div className="text-sm text-red-800 dark:text-red-200">
          <p className="font-semibold">Upload Error</p>
          <p data-testid="upload-error-message">{message}</p>
        </div>
      </div>
    </div>
  );
}
