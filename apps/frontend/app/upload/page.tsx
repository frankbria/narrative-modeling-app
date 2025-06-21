'use client';

import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Database, AlertCircle, CheckCircle } from 'lucide-react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { useRouter } from 'next/navigation';

export default function UploadPage() {
  const { completeStage } = useWorkflow();
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setError(null);
    setUploading(true);
    setUploadProgress(0);

    try {
      const token = await getAuthToken();
      const formData = new FormData();
      formData.append('file', file);

      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const response = JSON.parse(xhr.responseText);
          
          // Mark stage as complete and store dataset ID
          completeStage(WorkflowStage.DATA_LOADING, {
            datasetId: response.id,
            filename: file.name,
            timestamp: new Date().toISOString()
          });

          // Navigate to data profiling
          router.push(`/explore/${response.id}`);
        } else {
          setError('Upload failed. Please try again.');
          setUploading(false);
        }
      });

      xhr.addEventListener('error', () => {
        setError('Network error. Please check your connection.');
        setUploading(false);
      });

      xhr.open('POST', `${API_URL}/upload`);
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);

    } catch (err) {
      setError('Failed to upload file. Please try again.');
      setUploading(false);
    }
  }, [completeStage, router]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/json': ['.json']
    },
    maxFiles: 1,
    disabled: uploading
  });

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-md p-8">
        <h1 className="text-3xl font-bold mb-2 text-center">Upload Your Data</h1>
        <p className="text-gray-600 text-center mb-8">
          Start by uploading a CSV, Excel, or JSON file containing your data
        </p>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-blue-500 bg-blue-50'
              : uploading
              ? 'border-gray-300 bg-gray-50 cursor-not-allowed'
              : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }`}
        >
          <input {...getInputProps()} />
          
          {uploading ? (
            <div>
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600 mb-2">Uploading...</p>
              <div className="max-w-xs mx-auto">
                <div className="bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-600 h-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-sm text-gray-500 mt-2">{uploadProgress}%</p>
              </div>
            </div>
          ) : (
            <>
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-lg mb-2">
                {isDragActive
                  ? 'Drop your file here'
                  : 'Drag and drop your file here, or click to browse'
                }
              </p>
              <p className="text-sm text-gray-500">
                Supports CSV, Excel (XLS, XLSX), and JSON files up to 100MB
              </p>
            </>
          )}
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <div className="text-sm text-red-800">
              <p className="font-semibold">Upload Error</p>
              <p>{error}</p>
            </div>
          </div>
        )}

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <FileText className="w-8 h-8 text-blue-600 mb-2" />
            <h3 className="font-semibold mb-1">CSV Files</h3>
            <p className="text-sm text-gray-600">
              Standard comma-separated values with headers
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <FileText className="w-8 h-8 text-green-600 mb-2" />
            <h3 className="font-semibold mb-1">Excel Files</h3>
            <p className="text-sm text-gray-600">
              .xls and .xlsx formats supported
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <Database className="w-8 h-8 text-purple-600 mb-2" />
            <h3 className="font-semibold mb-1">Connect Database</h3>
            <p className="text-sm text-gray-600">
              Coming soon: Direct database connections
            </p>
          </div>
        </div>

        <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h3 className="font-semibold mb-2 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-blue-600" />
            What happens next?
          </h3>
          <ol className="text-sm text-gray-700 space-y-1 list-decimal list-inside">
            <li>Your data will be securely uploaded and processed</li>
            <li>We'll automatically analyze and profile your data</li>
            <li>You'll be guided through the 8-stage modeling workflow</li>
            <li>AI assistance will be available at every step</li>
          </ol>
        </div>
      </div>
    </div>
  );
}