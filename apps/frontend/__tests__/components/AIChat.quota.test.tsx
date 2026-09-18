/**
 * #767 AC5: AIChat renders the backend's quota sentence and opens the
 * plan-limit dialog store when /api/chat answers 402.
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { AIChat } from '@/components/AIChat'
import { planLimit } from '@/lib/billing/planLimit'
import { QuotaExceededError } from '@/lib/services/apiError'

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'user-123' } }, status: 'authenticated' }),
}))

// AIChat only reads contextString/isLoading/error/isAvailable off this hook
// (see lib/hooks/useDatasetChatContext.ts's return shape); stub it directly so
// this test doesn't also have to drive its own fetch/session/cache machinery.
jest.mock('@/lib/hooks/useDatasetChatContext', () => ({
  useDatasetChatContext: () => ({
    contextString: 'Dataset context summary',
    rawMarkdown: 'Dataset context summary',
    isLoading: false,
    error: null,
    isAvailable: true,
  }),
}))

const FULL_DETAIL = {
  error: 'quota_exceeded',
  metric: 'ai_calls',
  limit: 30,
  used: 30,
  tier: 'free',
  resets_at: '2026-10-01T00:00:00+00:00',
  message: 'You have used all 30 AI calls included in the free plan this month.',
  upgrade_available: true,
}

describe('AIChat quota handling (#767 AC5)', () => {
  beforeEach(() => {
    planLimit.dismiss()
  })

  it('shows the backend sentence and opens the plan-limit dialog on a 402', async () => {
    jest.useFakeTimers()

    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 402,
      statusText: 'Payment Required',
      json: async () => ({ detail: FULL_DETAIL }),
      text: async () => '',
    })

    render(<AIChat />)

    // Clear the 2s isPageLoading gate that disables the input/submit button.
    await act(async () => {
      jest.advanceTimersByTime(2000)
    })
    jest.useRealTimers()

    const input = screen.getByPlaceholderText('Type your message...')
    fireEvent.change(input, { target: { value: 'How many AI calls do I have left?' } })
    const form = input.closest('form')
    expect(form).not.toBeNull()
    fireEvent.submit(form!)

    await waitFor(() => {
      expect(screen.getByText(FULL_DETAIL.message)).toBeInTheDocument()
    })

    const err = planLimit.get()
    expect(err).toBeInstanceOf(QuotaExceededError)
    expect(err?.metric).toBe('ai_calls')
    expect(err?.limit).toBe(30)
    expect(err?.used).toBe(30)
    expect(err?.upgrade_available).toBe(true)
  })
})
