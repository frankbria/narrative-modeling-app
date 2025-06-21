import { useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'

interface ChunkUploadProgress {
  sessionId: string
  totalChunks: number
  uploadedChunks: number
  currentChunk: number
  progress: number
  bytesUploaded: number
  totalBytes: number
  speed: number // bytes per second
  remainingTime: number // seconds
  status: 'initializing' | 'uploading' | 'completed' | 'error' | 'paused'
  error?: string
}

interface ChunkedUploadOptions {
  chunkSize?: number // Default 5MB
  maxRetries?: number // Default 3
  onProgress?: (progress: ChunkUploadProgress) => void
  onComplete?: (fileId: string, response: any) => void
  onError?: (error: string) => void
}

export const useChunkedUpload = (options: ChunkedUploadOptions = {}) => {
  const { data: session } = useSession()
  const {
    chunkSize = 5 * 1024 * 1024, // 5MB default
    maxRetries = 3,
    onProgress,
    onComplete,
    onError
  } = options

  const [uploadState, setUploadState] = useState<ChunkUploadProgress | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const calculateHash = async (file: File): Promise<string> => {
    // Simple hash calculation for file integrity
    const buffer = await file.arrayBuffer()
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  }

  const initializeUpload = async (file: File): Promise<string> => {
    const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
    const fileHash = await calculateHash(file)
    
    const response = await fetch(`${backendUrl}/api/v1/upload/chunked/init`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${await getAuthToken()}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        filename: file.name,
        file_size: file.size.toString(),
        file_hash: fileHash
      })
    })

    if (!response.ok) {
      throw new Error(`Failed to initialize chunked upload: ${response.statusText}`)
    }

    const data = await response.json()
    return data.session_id
  }

  const uploadChunk = async (
    sessionId: string, 
    chunkNumber: number, 
    chunkData: Blob, 
    retryCount = 0
  ): Promise<boolean> => {
    try {
      const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
      const formData = new FormData()
      formData.append('file', chunkData, `chunk_${chunkNumber}`)

      const response = await fetch(`${backendUrl}/api/v1/upload/chunked/${sessionId}/chunk/${chunkNumber}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${await session?.getToken()}`
        },
        body: formData
      })

      if (!response.ok) {
        throw new Error(`Chunk ${chunkNumber} upload failed: ${response.statusText}`)
      }

      const result = await response.json()
      return result.complete || false
    } catch (error) {
      if (retryCount < maxRetries) {
        console.log(`Retrying chunk ${chunkNumber}, attempt ${retryCount + 1}`)
        await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1))) // Exponential backoff
        return uploadChunk(sessionId, chunkNumber, chunkData, retryCount + 1)
      }
      throw error
    }
  }

  const completeUpload = async (sessionId: string): Promise<any> => {
    const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
    
    const response = await fetch(`${backendUrl}/api/v1/upload/chunked/${sessionId}/complete`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${await session?.getToken()}`
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to complete upload: ${response.statusText}`)
    }

    return response.json()
  }

  const uploadFile = useCallback(async (file: File) => {
    if (!session) {
      throw new Error('User session not available')
    }

    setIsUploading(true)
    const startTime = Date.now()
    let bytesUploaded = 0

    try {
      // Calculate total chunks
      const totalChunks = Math.ceil(file.size / chunkSize)
      
      // Initialize upload session
      setUploadState({
        sessionId: '',
        totalChunks,
        uploadedChunks: 0,
        currentChunk: 0,
        progress: 0,
        bytesUploaded: 0,
        totalBytes: file.size,
        speed: 0,
        remainingTime: 0,
        status: 'initializing'
      })

      const sessionId = await initializeUpload(file)
      
      // Update state with session ID
      setUploadState(prev => prev ? { ...prev, sessionId, status: 'uploading' } : null)

      // Upload chunks sequentially
      for (let chunkNumber = 0; chunkNumber < totalChunks; chunkNumber++) {
        const start = chunkNumber * chunkSize
        const end = Math.min(start + chunkSize, file.size)
        const chunkData = file.slice(start, end)

        // Update current chunk
        setUploadState(prev => prev ? { ...prev, currentChunk: chunkNumber } : null)

        const isComplete = await uploadChunk(sessionId, chunkNumber, chunkData)
        
        // Update progress
        bytesUploaded = end
        const progress = (bytesUploaded / file.size) * 100
        const uploadedChunks = chunkNumber + 1
        const elapsedTime = (Date.now() - startTime) / 1000
        const speed = bytesUploaded / elapsedTime
        const remainingBytes = file.size - bytesUploaded
        const remainingTime = remainingBytes / speed

        const progressState: ChunkUploadProgress = {
          sessionId,
          totalChunks,
          uploadedChunks,
          currentChunk: chunkNumber,
          progress,
          bytesUploaded,
          totalBytes: file.size,
          speed,
          remainingTime: isFinite(remainingTime) ? remainingTime : 0,
          status: isComplete ? 'completed' : 'uploading'
        }

        setUploadState(progressState)
        onProgress?.(progressState)

        if (isComplete) break
      }

      // Complete the upload
      const result = await completeUpload(sessionId)
      
      setUploadState(prev => prev ? { ...prev, status: 'completed' } : null)
      onComplete?.(result.file_id, result)
      
      return result
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
      setUploadState(prev => prev ? { ...prev, status: 'error', error: errorMessage } : null)
      onError?.(errorMessage)
      throw error
    } finally {
      setIsUploading(false)
    }
  }, [session, chunkSize, maxRetries, onProgress, onComplete, onError])

  const resumeUpload = useCallback(async (sessionId: string) => {
    if (!session) {
      throw new Error('User session not available')
    }

    try {
      const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api$/, '')
      
      const response = await fetch(`${backendUrl}/api/v1/upload/chunked/${sessionId}/resume`, {
        headers: {
          'Authorization': `Bearer ${await session?.getToken()}`
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to get resume info: ${response.statusText}`)
      }

      const resumeInfo = await response.json()
      return resumeInfo
    } catch (error) {
      onError?.(error instanceof Error ? error.message : 'Failed to resume upload')
      throw error
    }
  }, [session, onError])

  const cancelUpload = useCallback(() => {
    setIsUploading(false)
    setUploadState(null)
  }, [])

  const resetUpload = useCallback(() => {
    setUploadState(null)
    setIsUploading(false)
  }, [])

  return {
    uploadFile,
    resumeUpload,
    cancelUpload,
    resetUpload,
    uploadState,
    isUploading
  }
}

export default useChunkedUpload