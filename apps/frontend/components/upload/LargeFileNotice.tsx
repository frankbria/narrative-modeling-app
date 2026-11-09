import React from 'react';
import { HugeiconsIcon } from '@hugeicons/react';
import { HardDriveIcon } from '@hugeicons/core-free-icons';
import { CHUNKED_UPLOAD_THRESHOLD, formatFileSize } from './uploadFlow';

export default function LargeFileNotice(props: { show: boolean; size: number }) {
  const { show, size } = props;
  if (!show) return null;
  return (
    <div className="mt-4 p-4 bg-warning/10 border border-warning/30 rounded-md">
      <div className="flex items-center space-x-2 mb-2">
        <HugeiconsIcon icon={HardDriveIcon} className="text-warning" size={16} />
        <span className="text-sm font-medium text-warning">Large File Detected</span>
      </div>
      <p className="text-sm text-warning">
        Your file is {formatFileSize(size)}, which exceeds our {formatFileSize(CHUNKED_UPLOAD_THRESHOLD)} threshold.{' '}
        We&apos;ll use chunked upload for optimal performance and reliability.
      </p>
      <ul className="text-xs text-warning mt-2 space-y-1">
        <li>• Upload can be resumed if interrupted</li>
        <li>• Progress tracking with detailed statistics</li>
        <li>• Automatic retry for failed chunks</li>
        <li>• PII scanning after complete upload</li>
      </ul>
    </div>
  );
}
