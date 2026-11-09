import React from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import { CancelCircleIcon, CheckmarkCircle01Icon, HardDriveIcon, Loading03Icon, PauseIcon, PlayIcon, Upload04Icon, ZapIcon } from '@hugeicons/core-free-icons'

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
        return 'text-primary'
      case 'uploading':
        return 'text-primary'
      case 'completed':
        return 'text-success'
      case 'error':
        return 'text-destructive'
      case 'paused':
        return 'text-warning'
      default:
        return 'text-muted-foreground'
    }
  }

  const getStatusIcon = () => {
    switch (progress.status) {
      case 'initializing':
        return <HugeiconsIcon icon={Upload04Icon} className="animate-pulse" size={20} />
      case 'uploading':
        return <HugeiconsIcon icon={Upload04Icon} className="animate-bounce" size={20} />
      case 'completed':
        return <HugeiconsIcon icon={CheckmarkCircle01Icon} size={20} />
      case 'error':
        return <HugeiconsIcon icon={CancelCircleIcon} size={20} />
      case 'paused':
        return <HugeiconsIcon icon={PauseIcon} size={20} />
      default:
        return <HugeiconsIcon icon={Upload04Icon} size={20} />
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
    <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
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
              className="p-2 text-warning hover:bg-warning/10 rounded-md transition-colors"
              title="Pause Upload"
            >
              <HugeiconsIcon icon={PauseIcon} size={16} />
            </button>
          )}
          {progress.status === 'paused' && onResume && (
            <button
              onClick={onResume}
              className="p-2 text-primary hover:bg-primary/10 rounded-md transition-colors"
              title="Resume Upload"
            >
              <HugeiconsIcon icon={PlayIcon} size={16} />
            </button>
          )}
          {(progress.status === 'uploading' || progress.status === 'paused') && onCancel && (
            <button
              onClick={onCancel}
              className="p-2 text-destructive hover:bg-destructive/10 rounded-md transition-colors"
              title="Cancel Upload"
            >
              <HugeiconsIcon icon={CancelCircleIcon} size={16} />
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
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Overall Progress</span>
            <span>{Math.round(progress.progress)}%</span>
          </div>
          <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
            <div 
              className={`h-full transition-all duration-300 ${
                progress.status === 'completed' 
                  ? 'bg-success' 
                  : progress.status === 'error'
                  ? 'bg-destructive'
                  : progress.status === 'paused'
                  ? 'bg-warning'
                  : 'bg-primary'
              }`}
              style={{ width: `${progress.progress}%` }}
            />
          </div>
        </div>

        {/* Chunks Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Chunks Uploaded</span>
            <span>{progress.uploadedChunks} / {progress.totalChunks}</span>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div 
              className="bg-primary h-full rounded-full transition-all duration-300"
              style={{ width: `${(progress.uploadedChunks / progress.totalChunks) * 100}%` }}
            />
          </div>
        </div>

        {/* Upload Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-border">
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <HugeiconsIcon icon={HardDriveIcon} className="text-muted-foreground" size={16} />
            </div>
            <div className="text-sm text-muted-foreground">Data Uploaded</div>
            <div className="font-semibold text-sm">
              {formatBytes(progress.bytesUploaded)} / {formatBytes(progress.totalBytes)}
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <HugeiconsIcon icon={ZapIcon} className="text-muted-foreground" size={16} />
            </div>
            <div className="text-sm text-muted-foreground">Upload Speed</div>
            <div className="font-semibold text-sm">
              {formatBytes(progress.speed)}/s
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <HugeiconsIcon icon={Loading03Icon} className="text-muted-foreground" size={16} />
            </div>
            <div className="text-sm text-muted-foreground">Time Remaining</div>
            <div className="font-semibold text-sm">
              {formatTime(progress.remainingTime)}
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <HugeiconsIcon icon={Upload04Icon} className="text-muted-foreground" size={16} />
            </div>
            <div className="text-sm text-muted-foreground">Session ID</div>
            <div className="font-semibold text-xs font-mono truncate">
              {progress.sessionId.slice(-8)}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {progress.status === 'error' && progress.error && (
          <div className="mt-4 p-3 bg-destructive/10 border border-destructive/30 rounded-md">
            <p className="text-sm text-destructive font-medium">Error Details:</p>
            <p className="text-sm text-destructive mt-1">{progress.error}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChunkedUploadProgress