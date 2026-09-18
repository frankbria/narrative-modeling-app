/**
 * #767 AC5: every metered surface that adopted apiError() rejects a 402
 * quota_exceeded body as a QuotaExceededError carrying the backend's real
 * numbers, and opens the single plan-limit dialog via the planLimit store.
 */
import { renderHook, act } from '@testing-library/react'
import { ModelService } from '@/lib/services/model'
import { DataIssuesService } from '@/lib/services/data-issues'
import useChunkedUpload from '@/lib/hooks/useChunkedUpload'
import { QuotaExceededError } from '@/lib/services/apiError'
import { planLimit } from '@/lib/billing/planLimit'

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'user-123' } }, status: 'authenticated' }),
}))

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok-123'),
}))

const FULL_DETAIL = {
  error: 'quota_exceeded',
  limit: 10,
  used: 10,
  tier: 'free',
  resets_at: '2026-10-01T00:00:00+00:00',
  message: 'You have used all 10 included in the free plan this month.',
  upgrade_available: true,
}

/** A fake 402 Response carrying the backend's quota_exceeded detail for `metric`. */
const quotaResponse = (metric: string) => ({
  ok: false,
  status: 402,
  statusText: 'Payment Required',
  json: async () => ({ detail: { ...FULL_DETAIL, metric } }),
  text: async () => '',
})

/** Assert the dialog store now holds a QuotaExceededError matching FULL_DETAIL. */
function expectDialogOpenedFor(metric: string) {
  const err = planLimit.get()
  expect(err).toBeInstanceOf(QuotaExceededError)
  expect(err?.metric).toBe(metric)
  expect(err?.limit).toBe(FULL_DETAIL.limit)
  expect(err?.used).toBe(FULL_DETAIL.used)
  expect(err?.resets_at).toBe(FULL_DETAIL.resets_at)
  expect(err?.upgrade_available).toBe(FULL_DETAIL.upgrade_available)
}

beforeEach(() => {
  planLimit.dismiss()
})

describe('#767 AC5: metered surfaces open the plan-limit dialog on a 402', () => {
  it('ModelService.trainModel — training_runs', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(quotaResponse('training_runs'))

    await expect(
      ModelService.trainModel({ dataset_id: 'd1', target_column: 'y' }, 'tok-123')
    ).rejects.toBeInstanceOf(QuotaExceededError)

    expectDialogOpenedFor('training_runs')
  })

  it('ModelService.predict — predictions', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(quotaResponse('predictions'))

    await expect(
      ModelService.predict('m1', { data: [{ x: 1 }] }, 'tok-123')
    ).rejects.toBeInstanceOf(QuotaExceededError)

    expectDialogOpenedFor('predictions')
  })

  it('ModelService.createBatchJob — predictions', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(quotaResponse('predictions'))

    const blob = new Blob(['a,b\n1,2'], { type: 'text/csv' })
    const file = Object.assign(blob, { name: 'data.csv' }) as unknown as File

    await expect(
      ModelService.createBatchJob('m1', file, {}, 'tok-123')
    ).rejects.toBeInstanceOf(QuotaExceededError)

    expectDialogOpenedFor('predictions')
  })

  it('ModelService.getErrorAnalysis — ai_calls', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(quotaResponse('ai_calls'))

    await expect(
      ModelService.getErrorAnalysis('m1', 'tok-123')
    ).rejects.toBeInstanceOf(QuotaExceededError)

    expectDialogOpenedFor('ai_calls')
  })

  it('DataIssuesService.detectIssues — ai_calls', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(quotaResponse('ai_calls'))

    await expect(
      DataIssuesService.detectIssues('d1', {}, 'tok-123')
    ).rejects.toBeInstanceOf(QuotaExceededError)

    expectDialogOpenedFor('ai_calls')
  })

  it('useChunkedUpload().uploadFile — uploads (init request)', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(quotaResponse('uploads'))
    Object.defineProperty(globalThis, 'crypto', {
      configurable: true,
      value: { subtle: { digest: jest.fn().mockResolvedValue(new ArrayBuffer(32)) } },
    })

    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 1024 }))
    const file = new File(['abcdefghij'], 'data.csv', { type: 'text/csv' })
    Object.defineProperty(file, 'arrayBuffer', { value: async () => new ArrayBuffer(8) })

    await act(async () => {
      await expect(result.current.uploadFile(file)).rejects.toBeInstanceOf(QuotaExceededError)
    })

    expectDialogOpenedFor('uploads')
  })
})
