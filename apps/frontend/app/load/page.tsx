'use client'

import { useUser } from '@clerk/nextjs'
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CheckCircle, XCircle, UploadCloud, FileText } from 'lucide-react'

export default function LoadPage() {
  const { isSignedIn } = useUser()
  const [file, setFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [isUploading, setIsUploading] = useState(false)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) {
      setUploadStatus('error')
      setFile(null)
      return
    }

    setFile(acceptedFiles[0])
    setUploadStatus('idle') // reset status
  }, [])

  const handleUpload = async () => {
    if (!file) return

    setIsUploading(true)

    try {
      // Simulate upload delay
      await new Promise((res) => setTimeout(res, 1000))

      // This is where you'd POST to your backend
      // const formData = new FormData()
      // formData.append('file', file)
      // await fetch('/api/upload', { method: 'POST', body: formData })

      setUploadStatus('success')
    } catch (err) {
      console.error('Upload error:', err)
      setUploadStatus('error')
    } finally {
      setIsUploading(false)
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    multiple: false,
  })

  if (!isSignedIn) return <p>Please log in to access this page.</p>

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Load Data</h1>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-8 transition-all cursor-pointer text-center ${
          isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
        }`}
      >
        <input {...getInputProps()} />
        {file ? (
          <div className="flex flex-col items-center space-y-2">
            <FileText className="text-blue-500" size={32} />
            <p className="text-sm text-gray-800">{file.name}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-2">
            <UploadCloud className="text-gray-400" size={32} />
            <p className="text-gray-700 text-lg">
              {isDragActive ? 'Drop it here...' : 'Drag a .csv, .txt, or .xlsx file or click to browse'}
            </p>
          </div>
        )}
      </div>

      {/* Upload Button */}
      {file && (
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={handleUpload}
            disabled={isUploading || uploadStatus === 'success'}
            className={`px-4 py-2 rounded text-white text-sm font-semibold transition-all ${
              uploadStatus === 'success'
                ? 'bg-green-500 cursor-default'
                : isUploading
                ? 'bg-blue-300 cursor-wait'
                : 'bg-blue-500 hover:bg-blue-600'
            }`}
          >
            {isUploading ? 'Uploading...' : uploadStatus === 'success' ? 'Uploaded' : 'Upload File'}
          </button>

          {/* Status indicator */}
          {uploadStatus === 'success' && (
            <div className="flex items-center text-green-600 space-x-1 text-sm">
              <CheckCircle size={18} />
              <span>Upload successful</span>
            </div>
          )}
          {uploadStatus === 'error' && (
            <div className="flex items-center text-red-600 space-x-1 text-sm">
              <XCircle size={18} />
              <span>Upload failed</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
