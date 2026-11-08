import { renderHook, waitFor } from '@testing-library/react'
import { useDatasetChatContext } from '@/lib/hooks/useDatasetChatContext'

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'u-1' } }, status: 'authenticated' }),
}))
jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok') }))

const OID = 'a'.repeat(24)
const answer = (status: number, body: unknown = {}) => ({ ok: status < 400, status, json: async () => body })

describe('useDatasetChatContext (#1167)', () => {
  it('resolves the user id to their latest dataset before asking for a summary', async () => {
    ;(global.fetch as jest.Mock)
      .mockResolvedValueOnce(answer(200, { _id: OID }))
      .mockResolvedValueOnce(answer(200, { rawMarkdown: 'Sales look healthy' }))
    const { result } = renderHook(() => useDatasetChatContext('u-latest'))
    await waitFor(() => expect(result.current.isAvailable).toBe(true))
    expect(result.current.contextString).toBe('Sales look healthy')
    expect(String((global.fetch as jest.Mock).mock.calls[1][0])).toContain(`/user_data/${OID}/ai-summary`)
  })

  it('treats a user with no dataset as "no analysis yet", not an error', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(answer(404))
    const { result } = renderHook(() => useDatasetChatContext('u-none'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current).toMatchObject({ error: null, isAvailable: false })
  })

  it('turns a validation failure into one plain sentence', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue(answer(422, { detail: [{ type: 'value_error' }] }))
    const { result } = renderHook(() => useDatasetChatContext('b'.repeat(24)))
    await waitFor(() => expect(result.current.error).toBe('We could not load the analysis of your data.'))
  })
})
