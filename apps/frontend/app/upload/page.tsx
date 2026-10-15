'use client';

import React from 'react';
import UploadSuccess from '@/components/upload/UploadSuccess';
import PIIWarning from '@/components/upload/PIIWarning';
import ChunkedProgressPanel from '@/components/upload/ChunkedProgressPanel';
import UploadDropzone from '@/components/upload/UploadDropzone';
import UploadButton from '@/components/upload/UploadButton';
import LargeFileNotice from '@/components/upload/LargeFileNotice';
import UploadErrorAlert from '@/components/upload/UploadErrorAlert';
import PreviewTable from '@/components/upload/PreviewTable';
import { FILE_TYPE_CARDS, WHAT_HAPPENS_NEXT } from '@/components/upload/UploadInfo';
import {
  showsLargeFileNotice,
  showsUploadButton,
  uploadButtonState,
  useUploadFlow,
} from '@/components/upload/useUploadFlow';

/** The upload page: a shell over `components/upload/`. */
export default function UploadPage() {
  const flow = useUploadFlow();
  const fileSize = Number(flow.file?.size);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-card rounded-lg shadow-md p-8">
        <h1 className="text-3xl font-bold mb-2 text-center">Upload Your Data</h1>
        <p className="text-muted-foreground text-center mb-8">
          Start by uploading a CSV, Excel, or JSON file containing your data
        </p>

        <UploadSuccess show={flow.showSuccessMessage} fileId={flow.uploadedFileId} onNext={flow.handleNextStep} />
        <PIIWarning
          show={flow.showPIIWarning}
          report={flow.piiData}
          confirming={flow.isConfirming}
          onConfirm={flow.handleConfirmPII}
          onCancel={flow.cancelPII}
        />
        <ChunkedProgressPanel
          active={flow.useChunkedUploadMode}
          progress={flow.chunkUploadState}
          onCancel={flow.cancelChunked}
        />
        <UploadDropzone file={flow.file} isLargeFile={flow.isLargeFile} onDrop={flow.onDrop} />
        <UploadButton show={showsUploadButton(flow)} state={uploadButtonState(flow)} onUpload={flow.handleUpload} />
        <LargeFileNotice show={showsLargeFileNotice(flow)} size={fileSize} />
        <UploadErrorAlert message={flow.errorMessage} />
        {FILE_TYPE_CARDS}
        <PreviewTable preview={flow.previewData} />
        {WHAT_HAPPENS_NEXT}
      </div>
    </div>
  );
}
