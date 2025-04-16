'use client'

import { useUser, useSession } from '@clerk/nextjs'
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CheckCircle, XCircle, UploadCloud, FileText, ArrowRight } from 'lucide-react'
import { useRouter } from 'next/navigation'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface SchemaField {
  field_name: string
  field_type: string
  data_type: string
  inferred_dtype: string
  unique_values: number
  missing_values: number
  example_values: string[]
  is_constant: boolean
  is_high_cardinality: boolean
}

interface PreviewData {
  headers: string[]
  previewData: Array<Array<string | number | boolean | null>>
  fileName: string
  fileType: string
  id?: string
  s3_url?: string
  schema?: SchemaField[]
}

export default function LoadPage() {
  const { isSignedIn } = useUser()
  const { session } = useSession()
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [isUploading, setIsUploading] = useState(false)
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isConfirming, setIsConfirming] = useState(false)
  const [showSuccessMessage, setShowSuccessMessage] = useState(false)
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    console.log('Files dropped:', acceptedFiles)
    if (acceptedFiles.length === 0) {
      setUploadStatus('error')
      setFile(null)
      setErrorMessage('No files were accepted')
      return
    }

    setFile(acceptedFiles[0])
    setUploadStatus('idle')
    setPreviewData(null)
    setErrorMessage(null)
    setShowSuccessMessage(false)
    setUploadedFileId(null)
    setIsUploading(false)
  }, [])

  const handleUpload = async () => {
    if (!file) return

    setIsUploading(true)
    setErrorMessage(null)
    console.log('Uploading file:', file.name, file.type)

    try {
      const formData = new FormData()
      formData.append('file', file)

      console.log('Sending request to /api/upload for preview')
      
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        }
      })

      console.log('Response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Error response:', errorText)
        throw new Error(`Upload failed: ${errorText}`)
      }

      const responseData = await response.json()
      console.log('Preview data:', responseData)
      
      if (!responseData.headers || !responseData.previewData) {
        throw new Error('Invalid response format: missing headers or preview data')
      }
      
      setPreviewData(responseData)
      setUploadStatus('success')
    } catch (err) {
      console.error('Upload error:', err)
      setUploadStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'An unknown error occurred')
      setFile(null)
    } finally {
      setIsUploading(false)
    }
  }

  const handleConfirmUpload = async () => {
    if (!file || !previewData) return
    
    setIsConfirming(true)
    try {
      console.log('Sending file to backend for storage')
      
      // Create a new FormData
      const formData = new FormData()
      formData.append('file', file)
      
      // Log file details
      console.log('File details:', {
        name: file.name,
        type: file.type,
        size: file.size
      })

      // Send the file directly to the backend
      const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
      const response = await fetch(`${backendUrl}/api/upload`, {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${await session?.getToken()}`
        }
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to store data: ${errorText}`)
      }

      const result = await response.json()
      console.log('Storage result:', result)
      
      // Show success message
      setUploadStatus('success')
      setErrorMessage(null)
      setShowSuccessMessage(true)
      setUploadedFileId(result.id)
      
      // Reset the form after successful upload
      setFile(null)
      setPreviewData(null)
    } catch (err) {
      console.error('Error:', err)
      setUploadStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsConfirming(false)
    }
  }

  const handleNextStep = () => {
    router.push('/review')
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
    <div className="p-6 ml-64">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Load Data</h1>

      {/* Success Message */}
      {showSuccessMessage && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-md">
          <div className="flex items-center">
            <CheckCircle className="text-green-500 mr-2" size={20} />
            <div>
              <p className="font-medium text-green-800">File uploaded successfully!</p>
              <p className="text-sm text-green-700">
                Your data has been processed and stored. You can now use it for analysis.
              </p>
              {uploadedFileId && (
                <p className="text-xs text-green-600 mt-1">
                  File ID: {uploadedFileId}
                </p>
              )}
              <button
                onClick={handleNextStep}
                className="mt-4 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors flex items-center space-x-2"
              >
                <span>Next Step</span>
                <ArrowRight size={16} />
                <span>Review Data</span>
              </button>
            </div>
          </div>
        </div>
      )}

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
      {file && !previewData && (
        <div className="mt-4 flex items-center justify-center">
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
        </div>
      )}

      {/* Status indicator */}
      {uploadStatus === 'success' && (
        <div className="mt-4 flex items-center justify-center text-green-600 space-x-1 text-sm">
          <CheckCircle size={18} />
          <span>Upload successful</span>
        </div>
      )}
      {uploadStatus === 'error' && (
        <div className="mt-4 flex items-center justify-center text-red-600 space-x-1 text-sm">
          <XCircle size={18} />
          <span>Upload failed</span>
        </div>
      )}

      {/* Error Message */}
      {errorMessage && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
          <p className="font-medium">Error:</p>
          <p>{errorMessage}</p>
        </div>
      )}

      {/* Preview Grid */}
      {previewData && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Preview Data</h2>
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-800">
                  {previewData.headers.map((header, index) => (
                    <TableHead key={index} className="text-white font-semibold">{header}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewData.previewData.map((row, rowIndex) => (
                  <TableRow 
                    key={rowIndex} 
                    className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                  >
                    {row.map((cell, cellIndex) => (
                      <TableCell key={cellIndex} className="text-gray-900">{cell}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Confirmation Button */}
          <div className="mt-6 flex justify-end">
            <button
              onClick={handleConfirmUpload}
              disabled={isConfirming}
              className={`px-6 py-2 rounded-md text-white font-medium transition-colors ${
                isConfirming
                  ? 'bg-blue-400 cursor-wait'
                  : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {isConfirming ? 'Saving...' : 'Confirm & Save Data'}
            </button>
          </div>
        </div>
      )}

      {/* Fallback Display */}
      {uploadStatus === 'success' && !previewData && !isConfirming && !showSuccessMessage && (
        <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="font-medium text-yellow-800">Upload successful but no preview data available.</p>
          <p className="text-sm text-yellow-700 mt-2">This might be due to an issue with the table component or the data format.</p>
        </div>
      )}
    </div>
  )
}
