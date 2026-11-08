import React from 'react';
import { ArrowRight, CheckCircle } from 'lucide-react';

/** The banner shown once a file is stored, with the way on to Explore. */
export default function UploadSuccess(props: { show: boolean; fileId: string | null; onNext: VoidFunction }) {
  const { show, fileId, onNext } = props;
  if (!show) return null;
  return (
    <div className="mb-6 p-4 bg-success/10 border border-success/30 rounded-md" data-testid="upload-status" role="status" aria-live="polite">
      <div className="flex items-center">
        <CheckCircle className="text-success mr-2" size={20} />
        <div>
          <p className="font-medium text-success">File uploaded successfully!</p>
          <p className="text-sm text-success">
            Your data has been processed and stored. You can now use it for analysis.
          </p>
          {fileId && (
            <p className="text-xs text-success mt-1" data-testid="file-id">
              File ID: {fileId}
            </p>
          )}
          <button
            onClick={onNext}
            data-testid="next-step-button"
            className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors flex items-center space-x-2"
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
