import React from 'react';
import { useDropzone } from 'react-dropzone';
import { FileText, HardDrive, Upload } from 'lucide-react';
import { formatFileSize } from './uploadFlow';

/** The file types the dropzone accepts (`__tests__/lib/reactDropzoneAccept.test.tsx` holds a copy). */
const ACCEPT = {
  'text/csv': ['.csv'],
  'text/plain': ['.txt'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/json': ['.json']
};

const DRAG_ACTIVE = 'border-blue-500 bg-blue-50 dark:bg-blue-950/40';
const DRAG_IDLE = 'border-border hover:border-blue-400 hover:bg-muted';

function ChosenFile(props: { file: File; isLargeFile: boolean }) {
  const { file, isLargeFile } = props;
  return (
    <div className="flex flex-col items-center space-y-3">
      <div className="flex items-center space-x-2">
        <FileText className="text-blue-500" size={32} />
        {isLargeFile && <HardDrive className="text-orange-500" size={20} />}
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-foreground">{file.name}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {formatFileSize(file.size)}
          {isLargeFile && (
            <span className="ml-2 px-2 py-1 bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200 rounded-md text-xs font-medium">
              Large File - Chunked Upload
            </span>
          )}
        </p>
      </div>
    </div>
  );
}

function DropPrompt(props: { isDragActive: boolean }) {
  const { isDragActive } = props;
  const prompt = isDragActive ? 'Drop it here...' : 'Drag a .csv, .txt, .xlsx, or .json file or click to browse';
  return (
    <div className="flex flex-col items-center space-y-2">
      <Upload className="w-12 h-12 text-gray-400" />
      <p className="text-lg text-foreground">
        {prompt}
      </p>
      <p className="text-sm text-muted-foreground">
        Supports CSV, Excel (XLS, XLSX), TXT, and JSON files up to 100MB
      </p>
    </div>
  );
}

interface DropzoneProps {
  file: File | null;
  isLargeFile: boolean;
  onDrop(files: File[]): void;
}

export default function UploadDropzone(props: DropzoneProps) {
  const { file, isLargeFile, onDrop } = props;
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: ACCEPT, multiple: false });
  const border = isDragActive ? DRAG_ACTIVE : DRAG_IDLE;
  return (
    <div
      {...getRootProps()}
      data-testid="upload-dropzone"
      className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${border}`}
    >
      <input {...getInputProps()} data-testid="file-input" />
      {file ? <ChosenFile file={file} isLargeFile={isLargeFile} /> : <DropPrompt isDragActive={isDragActive} />}
    </div>
  );
}
