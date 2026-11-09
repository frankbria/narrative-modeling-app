import React from 'react';
import { HugeiconsIcon } from '@/components/ui/icon';
import { AlertCircleIcon } from '@hugeicons/core-free-icons';

export default function UploadErrorAlert(props: { message: string | null }) {
  const { message } = props;
  if (!message) return null;
  return (
    <div className="mt-4 p-4 bg-destructive/10 border border-destructive/30 rounded-md" data-testid="upload-error" role="alert" aria-live="assertive">
      <div className="flex items-start gap-2">
        <HugeiconsIcon icon={AlertCircleIcon} className="w-5 h-5 text-destructive mt-0.5" />
        <div className="text-sm text-destructive">
          <p className="font-semibold">Upload Error</p>
          <p data-testid="upload-error-message">{message}</p>
        </div>
      </div>
    </div>
  );
}
