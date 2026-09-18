/**
 * The one place a plan-limit (402) error is parked so the single PlanLimitDialog
 * in the root layout can render it (#767 AC2).
 *
 * `apiError()` calls `show()` whenever it parses a `quota_exceeded` body, so every
 * surface that throws through it gets the dialog without touching its own catch
 * block; the error is still thrown, so inline error text keeps working too.
 */
import { useSyncExternalStore } from 'react'
import type { QuotaExceededError } from '@/lib/services/apiError'

// ponytail: module-level store + useSyncExternalStore; a context provider would
// need every service file to be rendered under it, and they are plain modules.
let current: QuotaExceededError | null = null
const listeners = new Set<() => void>()

const notify = () => listeners.forEach((listener) => listener())

export const planLimit = {
  show(error: QuotaExceededError) {
    current = error
    notify()
  },
  dismiss() {
    if (current === null) return
    current = null
    notify()
  },
  get: (): QuotaExceededError | null => current,
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  },
}

const getServerSnapshot = (): QuotaExceededError | null => null

export function usePlanLimit(): QuotaExceededError | null {
  return useSyncExternalStore(planLimit.subscribe, planLimit.get, getServerSnapshot)
}
