'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import type { ChunkedPiiPause, FlaggedPIIReport } from '@/lib/types/api';
import useChunkedUpload from '@/lib/hooks/useChunkedUpload';
import {
  CHUNKED_UPLOAD_THRESHOLD,
  messageOf,
  nameOf,
  postForm,
  readAnswer,
  toPreviewData,
  type PreviewData,
  type UploadAnswer,
} from './uploadFlow';

export type UploadStatus = 'idle' | 'success' | 'error';

/**
 * The upload page's state and its three ways to store a file: `/upload/secure`,
 * the PII confirmation, and the chunked upload for a large file.
 */
export function useUploadFlow() {
  const { completeStage, resetWorkflow, state } = useWorkflow();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [isUploading, setIsUploading] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null);
  const [showPIIWarning, setShowPIIWarning] = useState(false);
  const [piiData, setPiiData] = useState<FlaggedPIIReport | null>(null);
  // Set when the paused file is a chunked upload held on the server (#1122).
  const [piiSessionId, setPiiSessionId] = useState<string | null>(null);
  const [useChunkedUploadMode, setUseChunkedUploadMode] = useState(false);
  const [isLargeFile, setIsLargeFile] = useState(false);

  /** A file is stored: show its preview and complete the stage with its id. */
  function stored(answer: UploadAnswer, id: string) {
    const preview = toPreviewData(answer, nameOf(file), id);
    setPreviewData(preview);
    setUploadStatus('success');
    setShowSuccessMessage(true);
    setUploadedFileId(id);
    completeStage(WorkflowStage.DATA_LOADING, {
      datasetId: id,
      filename: preview.fileName,
      timestamp: new Date().toISOString()
    });
  }

  function failed(message: string) {
    setUploadStatus('error');
    setErrorMessage(message);
  }

  function chunkedStored(fileId: string, answer: UploadAnswer) {
    stored(answer, fileId);
    setUseChunkedUploadMode(false);
  }

  function chunkedFailed(error: string) {
    console.error('Chunk upload error:', error);
    failed(error);
    setUseChunkedUploadMode(false);
  }

  function chunkedPaused(pause: ChunkedPiiPause) {
    // High-risk PII: nothing is stored until the user chooses, as on /upload/secure.
    setPiiData(pause.pii_report);
    setPiiSessionId(pause.session_id);
    setShowPIIWarning(true);
    setUploadStatus('idle');
    setUseChunkedUploadMode(false);
  }

  const {
    uploadFile: uploadFileChunked,
    confirmUpload: confirmChunkedUpload,
    uploadState: chunkUploadState,
    isUploading: isChunkUploading,
    cancelUpload: cancelChunkUpload,
    resetUpload: resetChunkUpload
  } = useChunkedUpload({ onComplete: chunkedStored, onPiiDetected: chunkedPaused, onError: chunkedFailed });

  function select(selected: File) {
    // A confirm in flight owns the session; a new file would abort it and lose its answer.
    if (isConfirming) return;
    // A new upload starts a new workflow.
    if (state.datasetId) {
      resetWorkflow();
    }
    // A held chunked upload is dropped on the server too, not just forgotten here.
    if (piiSessionId) {
      cancelChunkUpload();
    }
    setFile(selected);
    setIsLargeFile(selected.size > CHUNKED_UPLOAD_THRESHOLD);
    setUploadStatus('idle');
    setPreviewData(null);
    setErrorMessage(null);
    setShowSuccessMessage(false);
    setUploadedFileId(null);
    setIsUploading(false);
    setShowPIIWarning(false);
    setPiiData(null);
    setPiiSessionId(null);
    setUseChunkedUploadMode(false);
    resetChunkUpload();
  }

  function onDrop(acceptedFiles: File[]) {
    if (acceptedFiles.length === 0) {
      setUploadStatus('error');
      setFile(null);
      setErrorMessage('No files were accepted');
      return;
    }
    select(acceptedFiles[0]);
  }

  async function uploadChunked(selected: File) {
    setUseChunkedUploadMode(true);
    try {
      await uploadFileChunked(selected);
    } catch (error) {
      // The hook's onError has already shown it.
      console.error('Chunked upload failed:', error);
    }
  }

  function secureAnswered(answer: UploadAnswer) {
    if (answer.status === 'pii_detected' && answer.requires_confirmation) {
      // High-risk PII: nothing is stored until the user chooses.
      setPiiData(answer.pii_report as FlaggedPIIReport);
      setShowPIIWarning(true);
      setUploadStatus('idle');
    } else if (answer.status === 'success') {
      stored(answer, answer.file_id as string);
    } else {
      throw new Error('Unexpected response format');
    }
  }

  async function uploadSecure(selected: File) {
    setIsUploading(true);
    setErrorMessage(null);
    setShowPIIWarning(false);
    try {
      const form = new FormData();
      form.append('file', selected);
      const response = await postForm('/upload/secure', form);
      secureAnswered(await readAnswer(response, `Upload failed: ${response.status}`));
    } catch (err) {
      console.error('Upload error:', err);
      failed(messageOf(err, 'An unknown error occurred'));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleUpload() {
    if (!file) return;
    if (isLargeFile) {
      await uploadChunked(file);
      return;
    }
    await uploadSecure(file);
  }

  async function confirm(selected: File, maskPII: boolean) {
    setIsConfirming(true);
    try {
      const form = new FormData();
      form.append('file', selected);
      form.append('mask_pii', maskPII.toString());
      const response = await postForm('/upload/confirm-pii-upload', form);
      const answer = await readAnswer(response, 'Failed to upload with PII');
      stored(answer, answer.file_id as string);
      setShowPIIWarning(false);
      setPiiData(null);
    } catch (err) {
      console.error('PII confirmation error:', err);
      failed(messageOf(err, 'An error occurred during PII confirmation'));
    } finally {
      setIsConfirming(false);
    }
  }

  async function confirmChunked(sessionId: string, maskPII: boolean) {
    setIsConfirming(true);
    try {
      // The hook's onComplete shows the stored dataset; onError has shown a failure.
      await confirmChunkedUpload(sessionId, maskPII);
      setShowPIIWarning(false);
      setPiiData(null);
      setPiiSessionId(null);
    } catch (err) {
      console.error('Chunked PII confirmation error:', err);
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleConfirmPII(maskPII: boolean) {
    if (!file || !piiData) return;
    if (piiSessionId) {
      await confirmChunked(piiSessionId, maskPII);
      return;
    }
    await confirm(file, maskPII);
  }

  function cancelPII() {
    if (piiSessionId) {
      // Drops the held file on the server.
      cancelChunkUpload();
      setPiiSessionId(null);
    }
    setShowPIIWarning(false);
    setPiiData(null);
    setFile(null);
  }

  function cancelChunked() {
    cancelChunkUpload();
    setUseChunkedUploadMode(false);
    setFile(null);
  }

  function handleNextStep() {
    if (uploadedFileId) {
      router.push(`/explore/${uploadedFileId}`);
    }
  }

  return {
    file,
    uploadStatus,
    isUploading,
    isChunkUploading,
    previewData,
    errorMessage,
    isConfirming,
    showSuccessMessage,
    uploadedFileId,
    showPIIWarning,
    piiData,
    useChunkedUploadMode,
    chunkUploadState,
    isLargeFile,
    onDrop,
    handleUpload,
    handleConfirmPII,
    cancelPII,
    cancelChunked,
    handleNextStep,
  };
}

export type UploadFlow = ReturnType<typeof useUploadFlow>;

/** A file is chosen and nothing has happened to it yet. */
export function showsUploadButton(flow: UploadFlow): boolean {
  return Boolean(flow.file) && !flow.previewData && !flow.showPIIWarning && !flow.useChunkedUploadMode;
}

export function showsLargeFileNotice(flow: UploadFlow): boolean {
  return Boolean(flow.file) && flow.isLargeFile && !flow.useChunkedUploadMode;
}

export function uploadButtonState(flow: UploadFlow) {
  return {
    busy: flow.isUploading || flow.isChunkUploading,
    success: flow.uploadStatus === 'success',
    large: flow.isLargeFile,
  };
}
