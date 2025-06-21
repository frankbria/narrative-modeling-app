'use client'

import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CheckCircle, XCircle, UploadCloud, FileText, ArrowRight, AlertTriangle, Shield, Eye, EyeOff, HardDrive } from 'lucide-react'
import { useRouter } from 'next/navigation'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useChunkedUpload from '@/lib/hooks/useChunkedUpload'
import ChunkedUploadProgress from '@/components/ChunkedUploadProgress'

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

interface PIIDetection {
  column: string
  field: string
  type: string
  confidence: number
  start?: number
  end?: number
}

interface PIIReport {
  has_pii: boolean
  detections: PIIDetection[]
  risk_level: string
  total_detections: number
  affected_columns: string[]
}

interface PreviewData {
  headers: string[]
  previewData: Array<Array<string | number | boolean | null>>
  fileName: string
  fileType: string
  id?: string
  s3_url?: string
  schema?: SchemaField[]
  pii_report?: PIIReport
  status?: string
  requires_confirmation?: boolean
}

export default function LoadPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [isUploading, setIsUploading] = useState(false)
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isConfirming, setIsConfirming] = useState(false)
  const [showSuccessMessage, setShowSuccessMessage] = useState(false)
  const [uploadedFileId, setUploadedFileId] = useState<string | null>(null)
  const [showPIIWarning, setShowPIIWarning] = useState(false)
  const [piiData, setPiiData] = useState<PIIReport | null>(null)
  const [useChunkedUploadMode, setUseChunkedUploadMode] = useState(false)
  const [isLargeFile, setIsLargeFile] = useState(false)

  // File size threshold for chunked upload (50MB)
  const CHUNKED_UPLOAD_THRESHOLD = 50 * 1024 * 1024

  // Initialize chunked upload hook
  const {
    uploadFile: uploadFileChunked,
    uploadState: chunkUploadState,
    isUploading: isChunkUploading,
    cancelUpload: cancelChunkUpload,
    resetUpload: resetChunkUpload
  } = useChunkedUpload({
    onProgress: (progress) => {
      console.log('Chunk upload progress:', progress)
    },
    onComplete: (fileId, response) => {
      console.log('Chunk upload completed:', { fileId, response })
      
      // Handle successful chunked upload
      const previewDataWithPII: PreviewData = {
        headers: Object.keys(response.preview?.[0] || {}),
        previewData: response.preview?.slice(0, 10).map((row: any) => 
          Object.values(row)
        ) || [],
        fileName: response.filename || file?.name || '',
        fileType: file?.name.split('.').pop()?.toLowerCase() || '',
        id: fileId,
        pii_report: response.pii_report,
        status: response.status
      }
      
      setPreviewData(previewDataWithPII)
      setUploadStatus('success')
      setShowSuccessMessage(true)
      setUploadedFileId(fileId)
      setUseChunkedUploadMode(false)
    },
    onError: (error) => {
      console.error('Chunk upload error:', error)
      setUploadStatus('error')
      setErrorMessage(error)
      setUseChunkedUploadMode(false)
    }
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    console.log('Files dropped:', acceptedFiles)
    if (acceptedFiles.length === 0) {
      setUploadStatus('error')
      setFile(null)
      setErrorMessage('No files were accepted')
      return
    }

    const selectedFile = acceptedFiles[0]
    const isLarge = selectedFile.size > CHUNKED_UPLOAD_THRESHOLD
    
    setFile(selectedFile)
    setIsLargeFile(isLarge)
    setUploadStatus('idle')
    setPreviewData(null)
    setErrorMessage(null)
    setShowSuccessMessage(false)
    setUploadedFileId(null)
    setIsUploading(false)
    setShowPIIWarning(false)
    setPiiData(null)
    setUseChunkedUploadMode(false)
    resetChunkUpload()
  }, [CHUNKED_UPLOAD_THRESHOLD, resetChunkUpload])

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const handleUpload = async () => {
    if (!file) return

    // Use chunked upload for large files
    if (isLargeFile) {
      setUseChunkedUploadMode(true)
      try {
        await uploadFileChunked(file)
      } catch (error) {
        console.error('Chunked upload failed:', error)
        // Error handling is done in the hook's onError callback
      }
      return
    }

    // Regular upload for smaller files
    setIsUploading(true)
    setErrorMessage(null)
    setShowPIIWarning(false)
    console.log('Uploading file:', file.name, file.type)

    try {
      const formData = new FormData()
      formData.append('file', file)

      console.log('Sending request to secure upload API')
      
      // Send directly to backend secure upload API
      const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
      const response = await fetch(`${backendUrl}/api/v1/upload/secure`, {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`
        }
      })

      console.log('Response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Error response:', errorText)
        throw new Error(`Upload failed: ${response.status} ${errorText}`)
      }

      const responseData = await response.json()
      console.log('Upload response:', responseData)
      
      // Handle different response types
      if (responseData.status === 'pii_detected' && responseData.requires_confirmation) {
        // High-risk PII detected, show warning
        setPiiData(responseData.pii_report)
        setShowPIIWarning(true)
        setUploadStatus('idle') // Keep in idle state for user decision
      } else if (responseData.status === 'success') {
        // Successful upload, show preview
        const previewDataWithPII: PreviewData = {
          headers: Object.keys(responseData.preview?.[0] || {}),
          previewData: responseData.preview?.slice(0, 10).map((row: any) => 
            Object.values(row)
          ) || [],
          fileName: responseData.filename || file.name,
          fileType: file.name.split('.').pop()?.toLowerCase() || '',
          id: responseData.file_id,
          pii_report: responseData.pii_report,
          status: responseData.status
        }
        
        setPreviewData(previewDataWithPII)
        setUploadStatus('success')
        setShowSuccessMessage(true)
        setUploadedFileId(responseData.file_id)
      } else {
        throw new Error('Unexpected response format')
      }
      
    } catch (err) {
      console.error('Upload error:', err)
      setUploadStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'An unknown error occurred')
    } finally {
      setIsUploading(false)
    }
  }

  const handleConfirmPII = async (maskPII: boolean = true) => {
    if (!file || !piiData) return
    
    setIsConfirming(true)
    try {
      console.log('Confirming PII upload with masking:', maskPII)
      
      const formData = new FormData()
      formData.append('file', file)
      formData.append('mask_pii', maskPII.toString())
      
      const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
      const response = await fetch(`${backendUrl}/api/v1/upload/confirm-pii-upload`, {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`
        }
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to upload with PII: ${errorText}`)
      }

      const result = await response.json()
      console.log('PII upload result:', result)
      
      // Show success and preview
      const previewDataWithPII: PreviewData = {
        headers: Object.keys(result.preview?.[0] || {}),
        previewData: result.preview?.slice(0, 10).map((row: any) => 
          Object.values(row)
        ) || [],
        fileName: result.filename || file.name,
        fileType: file.name.split('.').pop()?.toLowerCase() || '',
        id: result.file_id,
        pii_report: result.pii_report,
        status: result.status
      }
      
      setPreviewData(previewDataWithPII)
      setUploadStatus('success')
      setShowSuccessMessage(true)
      setUploadedFileId(result.file_id)
      setShowPIIWarning(false)
      setPiiData(null)
      
    } catch (err) {
      console.error('PII confirmation error:', err)
      setUploadStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'An error occurred during PII confirmation')
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

  if (!session) return <p>Please log in to access this page.</p>

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

      {/* PII Warning */}
      {showPIIWarning && piiData && (
        <div className="mb-6 p-6 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-center mb-4">
            <AlertTriangle className="text-amber-500 mr-3" size={24} />
            <div>
              <h3 className="font-bold text-amber-800 text-lg">Sensitive Data Detected</h3>
              <p className="text-amber-700">
                We've detected potentially sensitive information in your file that may require special handling.
              </p>
            </div>
          </div>

          <div className="bg-white rounded-md p-4 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-600">{piiData.total_detections}</div>
                <div className="text-sm text-gray-600">Total Detections</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{piiData.risk_level.toUpperCase()}</div>
                <div className="text-sm text-gray-600">Risk Level</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{piiData.affected_columns.length}</div>
                <div className="text-sm text-gray-600">Affected Columns</div>
              </div>
            </div>

            {piiData.detections.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-800 mb-2">Detected Sensitive Information:</h4>
                <div className="space-y-2">
                  {piiData.detections.slice(0, 5).map((detection, index) => (
                    <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                      <span className="text-sm font-medium text-gray-700">{detection.column}</span>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded">
                          {detection.type}
                        </span>
                        <span className="text-xs text-gray-500">
                          {Math.round(detection.confidence * 100)}% confidence
                        </span>
                      </div>
                    </div>
                  ))}
                  {piiData.detections.length > 5 && (
                    <div className="text-sm text-gray-500 italic">
                      ... and {piiData.detections.length - 5} more
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={() => handleConfirmPII(true)}
              disabled={isConfirming}
              className={`flex-1 px-4 py-3 rounded-md text-white font-medium transition-colors flex items-center justify-center space-x-2 ${
                isConfirming
                  ? 'bg-green-400 cursor-wait'
                  : 'bg-green-600 hover:bg-green-700'
              }`}
            >
              <Shield size={16} />
              <span>{isConfirming ? 'Processing...' : 'Upload with Data Masking'}</span>
              <EyeOff size={16} />
            </button>
            <button
              onClick={() => handleConfirmPII(false)}
              disabled={isConfirming}
              className={`flex-1 px-4 py-3 rounded-md font-medium transition-colors flex items-center justify-center space-x-2 ${
                isConfirming
                  ? 'bg-orange-400 cursor-wait text-white'
                  : 'bg-orange-100 hover:bg-orange-200 text-orange-800'
              }`}
            >
              <Eye size={16} />
              <span>{isConfirming ? 'Processing...' : 'Upload Original Data'}</span>
            </button>
            <button
              onClick={() => {
                setShowPIIWarning(false)
                setPiiData(null)
                setFile(null)
              }}
              className="px-4 py-3 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel Upload
            </button>
          </div>

          <div className="mt-4 text-xs text-gray-600">
            <p>
              <strong>Data Masking:</strong> Sensitive information will be replaced with placeholder values (e.g., ***@***.com for emails).
              <br />
              <strong>Original Data:</strong> Keep sensitive information as-is. Ensure you have proper authorization for handling this data.
            </p>
          </div>
        </div>
      )}

      {/* Chunked Upload Progress */}
      {useChunkedUploadMode && chunkUploadState && (
        <div className="mb-6">
          <ChunkedUploadProgress
            progress={chunkUploadState}
            onCancel={() => {
              cancelChunkUpload()
              setUseChunkedUploadMode(false)
              setFile(null)
            }}
          />
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
          <div className="flex flex-col items-center space-y-3">
            <div className="flex items-center space-x-2">
              <FileText className="text-blue-500" size={32} />
              {isLargeFile && <HardDrive className="text-orange-500" size={20} />}
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-gray-800">{file.name}</p>
              <p className="text-xs text-gray-600 mt-1">
                {formatFileSize(file.size)}
                {isLargeFile && (
                  <span className="ml-2 px-2 py-1 bg-orange-100 text-orange-800 rounded-md text-xs font-medium">
                    Large File - Chunked Upload
                  </span>
                )}
              </p>
            </div>
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
      {file && !previewData && !showPIIWarning && !useChunkedUploadMode && (
        <div className="mt-4 flex items-center justify-center">
          <button
            onClick={handleUpload}
            disabled={isUploading || isChunkUploading || uploadStatus === 'success'}
            className={`px-4 py-2 rounded text-white text-sm font-semibold transition-all ${
              uploadStatus === 'success'
                ? 'bg-green-500 cursor-default'
                : isUploading || isChunkUploading
                ? 'bg-blue-300 cursor-wait'
                : isLargeFile
                ? 'bg-orange-500 hover:bg-orange-600'
                : 'bg-blue-500 hover:bg-blue-600'
            }`}
          >
            {isUploading || isChunkUploading 
              ? (isLargeFile ? 'Starting Chunked Upload...' : 'Scanning for PII...') 
              : uploadStatus === 'success' 
              ? 'Uploaded' 
              : (isLargeFile ? 'Start Chunked Upload' : 'Upload & Scan File')
            }
          </button>
        </div>
      )}

      {/* Large File Info */}
      {file && isLargeFile && !useChunkedUploadMode && (
        <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-md">
          <div className="flex items-center space-x-2 mb-2">
            <HardDrive className="text-orange-500" size={16} />
            <span className="text-sm font-medium text-orange-800">Large File Detected</span>
          </div>
          <p className="text-sm text-orange-700">
            Your file is {formatFileSize(file.size)}, which exceeds our {formatFileSize(CHUNKED_UPLOAD_THRESHOLD)} threshold. 
            We'll use chunked upload for optimal performance and reliability.
          </p>
          <ul className="text-xs text-orange-600 mt-2 space-y-1">
            <li>• Upload can be resumed if interrupted</li>
            <li>• Progress tracking with detailed statistics</li>
            <li>• Automatic retry for failed chunks</li>
            <li>• PII scanning after complete upload</li>
          </ul>
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
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Preview Data</h2>
            {previewData.pii_report && (
              <div className="flex items-center space-x-2">
                {previewData.pii_report.has_pii ? (
                  <>
                    <Shield className="text-amber-500" size={16} />
                    <span className="text-sm text-amber-700 font-medium">
                      PII {previewData.pii_report.risk_level.toUpperCase()} RISK
                    </span>
                  </>
                ) : (
                  <>
                    <CheckCircle className="text-green-500" size={16} />
                    <span className="text-sm text-green-700 font-medium">NO PII DETECTED</span>
                  </>
                )}
              </div>
            )}
          </div>
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
