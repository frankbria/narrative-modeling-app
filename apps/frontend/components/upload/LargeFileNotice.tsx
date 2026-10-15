import React from 'react';
import { HardDrive } from 'lucide-react';
import { CHUNKED_UPLOAD_THRESHOLD, formatFileSize } from './uploadFlow';

export default function LargeFileNotice(props: { show: boolean; size: number }) {
  const { show, size } = props;
  if (!show) return null;
  return (
    <div className="mt-4 p-4 bg-orange-50 dark:bg-orange-950/40 border border-orange-200 dark:border-orange-900 rounded-md">
      <div className="flex items-center space-x-2 mb-2">
        <HardDrive className="text-orange-500" size={16} />
        <span className="text-sm font-medium text-orange-800 dark:text-orange-200">Large File Detected</span>
      </div>
      <p className="text-sm text-orange-700 dark:text-orange-300">
        Your file is {formatFileSize(size)}, which exceeds our {formatFileSize(CHUNKED_UPLOAD_THRESHOLD)} threshold.{' '}
        We&apos;ll use chunked upload for optimal performance and reliability.
      </p>
      <ul className="text-xs text-orange-600 mt-2 space-y-1">
        <li>• Upload can be resumed if interrupted</li>
        <li>• Progress tracking with detailed statistics</li>
        <li>• Automatic retry for failed chunks</li>
        <li>• PII scanning after complete upload</li>
      </ul>
    </div>
  );
}
