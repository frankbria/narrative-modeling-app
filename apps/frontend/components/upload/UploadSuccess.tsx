import React from 'react';
import { ArrowRight, CheckCircle } from 'lucide-react';

/** The banner shown once a file is stored, with the way on to Explore. */
export default function UploadSuccess(props: { show: boolean; fileId: string | null; onNext: VoidFunction }) {
  const { show, fileId, onNext } = props;
  if (!show) return null;
  return (
    <div className="mb-6 p-4 bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900 rounded-md" data-testid="upload-status" role="status" aria-live="polite">
      <div className="flex items-center">
        <CheckCircle className="text-green-500 mr-2" size={20} />
        <div>
          <p className="font-medium text-green-800 dark:text-green-200">File uploaded successfully!</p>
          <p className="text-sm text-green-700 dark:text-green-300">
            Your data has been processed and stored. You can now use it for analysis.
          </p>
          {fileId && (
            <p className="text-xs text-green-600 mt-1" data-testid="file-id">
              File ID: {fileId}
            </p>
          )}
          <button
            onClick={onNext}
            data-testid="next-step-button"
            className="mt-4 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors flex items-center space-x-2"
          >
            <span>Next Step</span>
            <ArrowRight size={16} />
            <span>Explore Data</span>
          </button>
        </div>
      </div>
    </div>
  );
}
