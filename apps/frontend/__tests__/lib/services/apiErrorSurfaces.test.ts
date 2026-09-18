/**
 * #767 diff-coverage follow-up: every `throw await apiError(response, ...)`
 * swap in model.ts / production.ts / data-issues.ts needs at least one non-OK
 * response exercised, or the branch is dead in coverage even though it is
 * mechanically identical everywhere. Table-driven over every static method
 * that has an `if (!response.ok)` branch, plus targeted coverage for the two
 * hooks (useFeatureSuggestions, useChunkedUpload) whose error branches aren't
 * reachable through a plain service call.
 */
import { renderHook, act } from '@testing-library/react'
import { ModelService } from '@/lib/services/model'
import { ProductionService } from '@/lib/services/production'
import { DataIssuesService } from '@/lib/services/data-issues'
import { ApiError, QuotaExceededError } from '@/lib/services/apiError'
import { useFeatureSuggestions } from '@/lib/hooks/useFeatureSuggestions'
import useChunkedUpload from '@/lib/hooks/useChunkedUpload'

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok-123'),
}))

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'user-123' } }, status: 'authenticated' }),
}))

const dummyFile = (): File => {
  const blob = new Blob(['a,b\n1,2'], { type: 'text/csv' })
  return Object.assign(blob, { name: 'data.csv' }) as unknown as File
}

/** A generic non-quota 503 the same shape a real upstream 5xx returns. */
const upstream503 = () => ({
  ok: false,
  status: 503,
  statusText: 'Service Unavailable',
  json: async () => ({ detail: 'upstream boom' }),
  text: async () => '',
})

type Case = [string, () => Promise<unknown>]

const modelCases: Case[] = [
  ['ModelService.trainModel', () => ModelService.trainModel({ dataset_id: 'd1', target_column: 'y' }, 'tok')],
  ['ModelService.getModeRecommendation', () => ModelService.getModeRecommendation('d1', 'tok')],
  ['ModelService.listModels', () => ModelService.listModels('tok')],
  ['ModelService.getModel', () => ModelService.getModel('m1', 'tok')],
  ['ModelService.getTrainingStatus', () => ModelService.getTrainingStatus('m1', 'tok')],
  ['ModelService.listTrainingJobs', () => ModelService.listTrainingJobs(undefined, 'tok')],
  ['ModelService.getTrainingLogs', () => ModelService.getTrainingLogs('m1', undefined, 'tok')],
  ['ModelService.cancelTraining', () => ModelService.cancelTraining('m1', 'tok')],
  ['ModelService.getEvaluation', () => ModelService.getEvaluation('m1', 'tok')],
  ['ModelService.getErrorAnalysis', () => ModelService.getErrorAnalysis('m1', 'tok')],
  ['ModelService.compareModels', () => ModelService.compareModels(['m1', 'm2'], 'tok')],
  ['ModelService.getModelVersions', () => ModelService.getModelVersions('m1', 'tok')],
  ['ModelService.promoteModelVersion', () => ModelService.promoteModelVersion('m1', 'tok')],
  ['ModelService.getShapSummary', () => ModelService.getShapSummary('m1', 'tok')],
  ['ModelService.predict', () => ModelService.predict('m1', { data: [{ x: 1 }] }, 'tok')],
  ['ModelService.getModelFeatures', () => ModelService.getModelFeatures('m1', 'tok')],
  ['ModelService.getSdkInfo', () => ModelService.getSdkInfo('m1', 'tok')],
  ['ModelService.getSdk', () => ModelService.getSdk('m1', 'python', 'tok')],
  ['ModelService.getSdkPostman', () => ModelService.getSdkPostman('m1', 'tok')],
  ['ModelService.createBatchJob', () => ModelService.createBatchJob('m1', dummyFile(), {}, 'tok')],
  ['ModelService.getBatchJob', () => ModelService.getBatchJob('j1', 'tok')],
  ['ModelService.getBatchJobProgress', () => ModelService.getBatchJobProgress('j1', 'tok')],
  ['ModelService.downloadBatchResults', () => ModelService.downloadBatchResults('j1', 'tok')],
  ['ModelService.cancelBatchJob', () => ModelService.cancelBatchJob('j1', 'tok')],
  ['ModelService.deleteModel', () => ModelService.deleteModel('m1', 'tok')],
  ['ModelService.deactivateModel', () => ModelService.deactivateModel('m1', 'tok')],
]

const productionCases: Case[] = [
  ['ProductionService.createAPIKey', () => ProductionService.createAPIKey({ name: 'k1' }, 'tok')],
  ['ProductionService.listAPIKeys', () => ProductionService.listAPIKeys('tok')],
  ['ProductionService.revokeAPIKey', () => ProductionService.revokeAPIKey('k1', 'tok')],
  ['ProductionService.getModelMetrics', () => ProductionService.getModelMetrics('m1', 24, 'tok')],
  ['ProductionService.getUsageTimeline', () => ProductionService.getUsageTimeline('m1', 24, 'tok')],
  ['ProductionService.getDeploymentHealth', () => ProductionService.getDeploymentHealth('m1', 24, 'tok')],
  ['ProductionService.getUsageOverview', () => ProductionService.getUsageOverview('tok')],
  ['ProductionService.getAPIKeyUsage', () => ProductionService.getAPIKeyUsage('tok')],
  ['ProductionService.getPredictionLogs', () => ProductionService.getPredictionLogs('m1', 10, 'tok')],
  ['ProductionService.getPredictionDistribution', () => ProductionService.getPredictionDistribution('m1', 24, 'tok')],
]

const dataIssuesCases: Case[] = [
  ['DataIssuesService.detectIssues', () => DataIssuesService.detectIssues('d1', {}, 'tok')],
  ['DataIssuesService.getDatasetIssues', () => DataIssuesService.getDatasetIssues('d1', 'tok')],
  ['DataIssuesService.previewFix', () => DataIssuesService.previewFix('d1', 'i1', 'tok')],
  ['DataIssuesService.applyFix', () => DataIssuesService.applyFix('d1', 'i1', 'tok')],
  ['DataIssuesService.batchApplyFixes', () => DataIssuesService.batchApplyFixes('d1', ['i1'], 'tok')],
  ['DataIssuesService.getIssueHistory', () => DataIssuesService.getIssueHistory('d1', 'tok')],
]

describe('every metered-service method surfaces a non-OK response as an ApiError', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockResolvedValue(upstream503())
  })

  it.each([...modelCases, ...productionCases, ...dataIssuesCases])(
    '%s rejects with the backend detail via ApiError',
    async (_label, callMethod) => {
      let caught: unknown
      try {
        await callMethod()
        throw new Error('expected the call to reject')
      } catch (err) {
        caught = err
      }
      expect(caught).toBeInstanceOf(ApiError)
      expect(caught).toMatchObject({ status: 503, message: 'upstream boom' })
    }
  )
})

describe('useFeatureSuggestions surfaces the backend detail as hook error state', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockResolvedValue(upstream503())
  })

  it('fetchSuggestions', async () => {
    const { result } = renderHook(() => useFeatureSuggestions({ datasetId: 'd1' }))
    await act(async () => {
      await result.current.fetchSuggestions()
    })
    expect(result.current.error).toBe('upstream boom')
  })

  it('acceptSuggestion', async () => {
    const { result } = renderHook(() => useFeatureSuggestions({ datasetId: 'd1' }))
    await act(async () => {
      await result.current.acceptSuggestion('s1')
    })
    expect(result.current.error).toBe('upstream boom')
  })

  it('rejectSuggestion', async () => {
    const { result } = renderHook(() => useFeatureSuggestions({ datasetId: 'd1' }))
    await act(async () => {
      await result.current.rejectSuggestion('s1')
    })
    expect(result.current.error).toBe('upstream boom')
  })

  it('loadMore', async () => {
    const { result } = renderHook(() => useFeatureSuggestions({ datasetId: 'd1' }))
    await act(async () => {
      await result.current.loadMore([])
    })
    expect(result.current.error).toBe('upstream boom')
  })
})

describe('useChunkedUpload surfaces non-OK responses and skips retry on quota', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'crypto', {
      configurable: true,
      value: { subtle: { digest: jest.fn().mockResolvedValue(new ArrayBuffer(32)) } },
    })
  })

  const makeFile = () => {
    const file = new File(['abcdefghij'], 'data.csv', { type: 'text/csv' })
    Object.defineProperty(file, 'arrayBuffer', { value: async () => new ArrayBuffer(8) })
    return file
  }

  // Pins the retry-skip at the QuotaExceededError check in uploadChunk's catch
  // block: a 402 on the very first chunk must fail immediately, never retry.
  it('a 402 quota body on the first chunk is not retried', async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({ ok: true, statusText: 'OK', json: async () => ({ session_id: 's1' }) }) // init
      .mockResolvedValueOnce({
        ok: false,
        status: 402,
        statusText: 'Payment Required',
        json: async () => ({
          detail: { error: 'quota_exceeded', metric: 'uploads', message: 'Upload quota reached.' },
        }),
        text: async () => '',
      }) // chunk 0
    ;(global.fetch as jest.Mock) = fetchMock

    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 1024, maxRetries: 3 }))

    await act(async () => {
      await expect(result.current.uploadFile(makeFile())).rejects.toBeInstanceOf(QuotaExceededError)
    })

    // init + exactly one chunk attempt — no retry, no further calls.
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('a 503 on the complete request surfaces as an ApiError with the backend detail', async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({ ok: true, statusText: 'OK', json: async () => ({ session_id: 's2' }) }) // init
      .mockResolvedValueOnce({ ok: true, statusText: 'OK', json: async () => ({ complete: true }) }) // chunk 0
      .mockResolvedValueOnce(upstream503()) // complete
    ;(global.fetch as jest.Mock) = fetchMock

    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 1024 }))

    await act(async () => {
      await expect(result.current.uploadFile(makeFile())).rejects.toMatchObject({
        status: 503,
        message: 'upstream boom',
      })
    })
  })

  it('resumeUpload surfaces a 503 as an ApiError with the backend detail', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(upstream503())

    const { result } = renderHook(() => useChunkedUpload())

    await act(async () => {
      await expect(result.current.resumeUpload('s1')).rejects.toMatchObject({
        status: 503,
        message: 'upstream boom',
      })
    })
  })
})
