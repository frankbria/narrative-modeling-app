import React from 'react';
import ChunkedUploadProgress from '@/components/ChunkedUploadProgress';

type Progress = React.ComponentProps<typeof ChunkedUploadProgress>['progress'];

export default function ChunkedProgressPanel(props: { active: boolean; progress: Progress | null; onCancel: VoidFunction }) {
  const { active, progress, onCancel } = props;
  if (!active || !progress) return null;
  return (
    <div className="mb-6">
      <ChunkedUploadProgress progress={progress} onCancel={onCancel} />
    </div>
  );
}
