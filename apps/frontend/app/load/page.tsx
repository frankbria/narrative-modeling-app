'use client'

import { useUser } from '@clerk/nextjs'
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CheckCircle, XCircle, UploadCloud, FileText } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface PreviewData {
  headers: string[]
  previewData: (string | number | boolean | null)[][]
  fileName: string
  fileType: string
}

export default function LoadPage() {
  const { isSignedIn } = useUser()
  const [file, setFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [isUploading, setIsUploading] = useState(false)
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isConfirming, setIsConfirming] = useState(false)

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
  }, [])

  const handleUpload = async () => {
    if (!file) return

    setIsUploading(true)
    setErrorMessage(null)
    console.log('Uploading file:', file.name, file.type)

    try {
      const formData = new FormData()
      formData.append('file', file)

      console.log('Sending request to /api/upload')
      
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      console.log('Response status:', response.status)
      
      // Check if the response is ok before trying to parse JSON
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Error response:', errorText)
        throw new Error(`Upload failed: ${errorText}`)
      }

      // Try to parse the response as JSON
      let responseData
      try {
        const text = await response.text()
        console.log('Raw response:', text)
        responseData = JSON.parse(text)
      } catch (parseError) {
        console.error('JSON parse error:', parseError)
        throw new Error('Failed to parse server response')
      }
      
      console.log('Response data:', responseData)
      
      if (!responseData.headers || !responseData.previewData) {
        throw new Error('Invalid response format: missing headers or preview data')
      }
      
      setPreviewData(responseData)
      setUploadStatus('success')
    } catch (err) {
      console.error('Upload error:', err)
      setUploadStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'An unknown error occurred')
    } finally {
      setIsUploading(false)
    }
  }

  const handleConfirmUpload = async () => {
    if (!previewData) return
    
    setIsConfirming(true)
    try {
      // TODO: Implement the actual database write
      console.log('Writing to database:', previewData)
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      // Show success message
      setUploadStatus('success')
      setErrorMessage(null)
    } catch (err) {
      console.error('Database write error:', err)
      setUploadStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'Failed to save data to database')
    } finally {
      setIsConfirming(false)
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
      {file && !previewData && (
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
      {uploadStatus === 'success' && !previewData && (
        <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="font-medium text-yellow-800">Upload successful but no preview data available.</p>
          <p className="text-sm text-yellow-700 mt-2">This might be due to an issue with the table component or the data format.</p>
        </div>
      )}
    </div>
  )
}
