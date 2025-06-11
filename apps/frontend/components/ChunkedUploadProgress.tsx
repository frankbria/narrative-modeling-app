import React from 'react'
import { Upload, Clock, HardDrive, Zap, CheckCircle, XCircle, Pause, Play } from 'lucide-react'

interface ChunkUploadProgress {
  sessionId: string
  totalChunks: number
  uploadedChunks: number
  currentChunk: number
  progress: number
  bytesUploaded: number
  totalBytes: number
  speed: number
  remainingTime: number
  status: 'initializing' | 'uploading' | 'completed' | 'error' | 'paused'
  error?: string
}

interface ChunkedUploadProgressProps {
  progress: ChunkUploadProgress
  onCancel?: () => void
  onResume?: () => void
  onPause?: () => void
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatTime = (seconds: number): string => {
  if (!isFinite(seconds) || seconds < 0) return '--'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${remainingSeconds}s`
  } else if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  } else {
    return `${remainingSeconds}s`
  }
}

const ChunkedUploadProgress: React.FC<ChunkedUploadProgressProps> = ({
  progress,
  onCancel,
  onResume,
  onPause
}) => {
  const getStatusColor = () => {
    switch (progress.status) {
      case 'initializing':
        return 'text-blue-600'
      case 'uploading':
        return 'text-blue-600'
      case 'completed':
        return 'text-green-600'
      case 'error':
        return 'text-red-600'
      case 'paused':
        return 'text-yellow-600'
      default:
        return 'text-gray-600'
    }
  }

  const getStatusIcon = () => {
    switch (progress.status) {
      case 'initializing':
        return <Upload className="animate-pulse" size={20} />
      case 'uploading':
        return <Upload className="animate-bounce" size={20} />
      case 'completed':
        return <CheckCircle size={20} />
      case 'error':
        return <XCircle size={20} />
      case 'paused':
        return <Pause size={20} />
      default:
        return <Upload size={20} />
    }
  }

  const getStatusText = () => {
    switch (progress.status) {
      case 'initializing':
        return 'Initializing upload...'
      case 'uploading':
        return `Uploading chunk ${progress.currentChunk + 1} of ${progress.totalChunks}`
      case 'completed':
        return 'Upload completed successfully!'
      case 'error':
        return `Upload failed: ${progress.error}`
      case 'paused':
        return 'Upload paused'
      default:
        return 'Unknown status'
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className={getStatusColor()}>
            {getStatusIcon()}
          </div>
          <h3 className="font-semibold text-lg">Chunked Upload Progress</h3>
        </div>
        <div className="flex items-center space-x-2">
          {progress.status === 'uploading' && onPause && (
            <button
              onClick={onPause}
              className="p-2 text-yellow-600 hover:bg-yellow-50 rounded-md transition-colors"
              title="Pause Upload"
            >
              <Pause size={16} />
            </button>
          )}
          {progress.status === 'paused' && onResume && (
            <button
              onClick={onResume}
              className="p-2 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
              title="Resume Upload"
            >
              <Play size={16} />
            </button>
          )}
          {(progress.status === 'uploading' || progress.status === 'paused') && onCancel && (
            <button
              onClick={onCancel}
              className="p-2 text-red-600 hover:bg-red-50 rounded-md transition-colors"
              title="Cancel Upload"
            >
              <XCircle size={16} />
            </button>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {/* Status Text */}
        <p className={`text-sm font-medium ${getStatusColor()}`}>
          {getStatusText()}
        </p>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Overall Progress</span>
            <span>{Math.round(progress.progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
            <div 
              className={`h-full transition-all duration-300 ${
                progress.status === 'completed' 
                  ? 'bg-green-500' 
                  : progress.status === 'error'
                  ? 'bg-red-500'
                  : progress.status === 'paused'
                  ? 'bg-yellow-500'
                  : 'bg-blue-500'
              }`}
              style={{ width: `${progress.progress}%` }}
            />
          </div>
        </div>

        {/* Chunks Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Chunks Uploaded</span>
            <span>{progress.uploadedChunks} / {progress.totalChunks}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-400 h-full rounded-full transition-all duration-300"
              style={{ width: `${(progress.uploadedChunks / progress.totalChunks) * 100}%` }}
            />
          </div>
        </div>

        {/* Upload Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-100">
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <HardDrive className="text-gray-500" size={16} />
            </div>
            <div className="text-sm text-gray-600">Data Uploaded</div>
            <div className="font-semibold text-sm">
              {formatBytes(progress.bytesUploaded)} / {formatBytes(progress.totalBytes)}
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Zap className="text-gray-500" size={16} />
            </div>
            <div className="text-sm text-gray-600">Upload Speed</div>
            <div className="font-semibold text-sm">
              {formatBytes(progress.speed)}/s
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Clock className="text-gray-500" size={16} />
            </div>
            <div className="text-sm text-gray-600">Time Remaining</div>
            <div className="font-semibold text-sm">
              {formatTime(progress.remainingTime)}
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Upload className="text-gray-500" size={16} />
            </div>
            <div className="text-sm text-gray-600">Session ID</div>
            <div className="font-semibold text-xs font-mono truncate">
              {progress.sessionId.slice(-8)}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {progress.status === 'error' && progress.error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700 font-medium">Error Details:</p>
            <p className="text-sm text-red-600 mt-1">{progress.error}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChunkedUploadProgress