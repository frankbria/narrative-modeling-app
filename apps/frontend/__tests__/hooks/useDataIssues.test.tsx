/**
 * useDataIssues hands the backend the minted API JWT (#527) — it used to read
 * `(session as any).accessToken`, the OAuth provider's credential.
 */
import { renderHook, act } from '@testing-library/react'

const mockSession: { data: Record<string, unknown> | null } = { data: { apiToken: 'minted.api.jwt' } }
jest.mock('next-auth/react', () => ({ useSession: () => mockSession }))

jest.mock('@/lib/services/data-issues', () => ({
  DataIssuesService: {
    detectIssues: jest.fn(),
    getDatasetIssues: jest.fn(),
    previewFix: jest.fn(),
    applyFix: jest.fn(),
    batchApplyFixes: jest.fn(),
  },
}))

import { DataIssuesService } from '@/lib/services/data-issues'
import { useDataIssues } from '@/hooks/useDataIssues'

const detect = DataIssuesService.detectIssues as jest.Mock
const getIssues = DataIssuesService.getDatasetIssues as jest.Mock

describe('useDataIssues bearer', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockSession.data = { apiToken: 'minted.api.jwt', accessToken: 'ya29.provider' }
    detect.mockResolvedValue({ issues: [], summary: null, record_id: 'r1' })
    getIssues.mockResolvedValue({ issues: [], summary: null, record_id: 'r1' })
  })

  it('passes session.apiToken — never the provider token — to the service', async () => {
    const { result } = renderHook(() => useDataIssues('ds-1'))
    await act(async () => {
      await result.current.detectIssues()
      await result.current.refreshIssues()
    })
    expect(detect).toHaveBeenCalledWith('ds-1', expect.anything(), 'minted.api.jwt')
    expect(getIssues).toHaveBeenCalledWith('ds-1', 'minted.api.jwt')
    expect(JSON.stringify(detect.mock.calls)).not.toContain('ya29.')
  })

  it('passes null, not a placeholder, when there is no API token', async () => {
    mockSession.data = { accessToken: 'ya29.provider' }
    const { result } = renderHook(() => useDataIssues('ds-1'))
    await act(async () => {
      await result.current.detectIssues()
    })
    expect(detect).toHaveBeenCalledWith('ds-1', expect.anything(), null)
  })
})
