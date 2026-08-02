/**
 * Contract for useAsyncData (#393).
 *
 * The hook exists to remove `react-hooks/set-state-in-effect` violations without
 * losing the refetch spinner. Both halves matter, so both are asserted here:
 *
 *  - `loading` must return to true the moment a dependency changes, BEFORE the new
 *    promise resolves. That is the behaviour the 46 hand-written `setLoading(true)`
 *    calls provided, and the thing that silently disappears if the hook is wrong.
 *  - It must do that WITHOUT calling setState during the effect — otherwise it
 *    reintroduces the exact violation it is meant to remove, in one shared place.
 *
 * The second property is enforced by lint, not here. What this file guards is that
 * the derived-loading mechanism actually behaves like the code it replaces.
 */
import { renderHook, act, waitFor } from '@testing-library/react'

import { useAsyncData } from '@/lib/hooks/useAsyncData'

/** A promise whose resolution we control, so we can observe the pending window. */
function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useAsyncData', () => {
  it('starts in a loading state before anything resolves', () => {
    const d = deferred<string>()
    const { result } = renderHook(() => useAsyncData(() => d.promise, []))

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toBeNull()
  })

  it('exposes data and clears loading once resolved', async () => {
    const d = deferred<string>()
    const { result } = renderHook(() => useAsyncData(() => d.promise, []))

    await act(async () => {
      d.resolve('hello')
      await d.promise
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.data).toBe('hello')
    expect(result.current.error).toBeNull()
  })

  it('surfaces a message and clears loading on rejection', async () => {
    const d = deferred<string>()
    const { result } = renderHook(() => useAsyncData(() => d.promise, []))

    await act(async () => {
      d.reject(new Error('boom'))
      await d.promise.catch(() => {})
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBe('boom')
    expect(result.current.data).toBeUndefined()
  })

  // The regression this whole refactor risks introducing.
  it('returns to loading when a dependency changes, before the refetch resolves', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    let current = first

    const { result, rerender } = renderHook(
      ({ tab }: { tab: string }) => useAsyncData(() => current.promise, [tab]),
      { initialProps: { tab: 'all' } },
    )

    await act(async () => {
      first.resolve('all-data')
      await first.promise
    })
    expect(result.current.loading).toBe(false)
    expect(result.current.data).toBe('all-data')

    // Dependency changes: the spinner must come back immediately, while the
    // previous result is still the only data we have.
    current = second
    rerender({ tab: 'running' })
    expect(result.current.loading).toBe(true)

    await act(async () => {
      second.resolve('running-data')
      await second.promise
    })
    expect(result.current.loading).toBe(false)
    expect(result.current.data).toBe('running-data')
  })

  it('does not refetch when deps are unchanged across rerenders', async () => {
    const loader = jest.fn().mockResolvedValue('x')
    const { result, rerender } = renderHook(() => useAsyncData(loader, ['stable']))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(loader).toHaveBeenCalledTimes(1)

    rerender()
    rerender()

    expect(loader).toHaveBeenCalledTimes(1)
  })

  it('ignores a stale response that resolves after a newer request', async () => {
    const slowFirst = deferred<string>()
    const fastSecond = deferred<string>()
    let current = slowFirst

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useAsyncData(() => current.promise, [id]),
      { initialProps: { id: 'a' } },
    )

    current = fastSecond
    rerender({ id: 'b' })

    await act(async () => {
      fastSecond.resolve('b-data')
      await fastSecond.promise
    })
    expect(result.current.data).toBe('b-data')

    // The abandoned first request lands late. It must not overwrite 'b'.
    await act(async () => {
      slowFirst.resolve('a-data')
      await slowFirst.promise
    })

    expect(result.current.data).toBe('b-data')
    expect(result.current.loading).toBe(false)
  })

  it('reload() refetches and shows loading again', async () => {
    const loader = jest.fn().mockResolvedValue('v1')
    const { result } = renderHook(() => useAsyncData(loader, []))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(loader).toHaveBeenCalledTimes(1)

    loader.mockResolvedValue('v2')
    act(() => {
      result.current.reload()
    })

    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBe('v2')
    expect(loader).toHaveBeenCalledTimes(2)
  })

  it('uses the latest loader closure without refetching on every render', async () => {
    // Call sites pass an inline arrow, so `loader` is a new function every render.
    // Refetching on identity would loop forever; using a stale closure would read
    // outdated props. It must do neither.
    let captured = 'first'
    const calls: string[] = []
    const { result, rerender } = renderHook(
      ({ token }: { token: string }) =>
        useAsyncData(async () => {
          calls.push(token)
          return captured
        }, ['fixed']),
      { initialProps: { token: 'first' } },
    )

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(calls).toEqual(['first'])

    captured = 'second'
    rerender({ token: 'second' })
    rerender({ token: 'second' })
    expect(calls).toEqual(['first']) // deps unchanged -> no refetch

    act(() => {
      result.current.reload()
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(calls).toEqual(['first', 'second']) // reload used the CURRENT closure
    expect(result.current.data).toBe('second')
  })

  it('skips the request when enabled is false and reports not-loading', async () => {
    // Many call sites guard on session/id: `if (session && modelId) fetch()`.
    const loader = jest.fn().mockResolvedValue('x')
    const { result, rerender } = renderHook(
      ({ on }: { on: boolean }) => useAsyncData(loader, ['k'], { enabled: on }),
      { initialProps: { on: false } },
    )

    expect(loader).not.toHaveBeenCalled()
    expect(result.current.loading).toBe(false)

    rerender({ on: true })
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(loader).toHaveBeenCalledTimes(1)
    expect(result.current.data).toBe('x')
  })
})

describe('useAsyncData keepPreviousData', () => {
  function deferred2<T>() {
    let resolve!: (v: T) => void
    const promise = new Promise<T>((res) => {
      resolve = res
    })
    return { promise, resolve }
  }

  it('drops previous data on a key change by default', async () => {
    const first = deferred2<string>()
    const second = deferred2<string>()
    let current = first
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useAsyncData(() => current.promise, [id]),
      { initialProps: { id: 'a' } },
    )
    await act(async () => {
      first.resolve('a-data')
      await first.promise
    })

    current = second
    rerender({ id: 'b' })

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('keeps previous data under the spinner when opted in', async () => {
    const first = deferred2<string>()
    const second = deferred2<string>()
    let current = first
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) =>
        useAsyncData(() => current.promise, [id], { keepPreviousData: true }),
      { initialProps: { id: 'a' } },
    )
    await act(async () => {
      first.resolve('a-data')
      await first.promise
    })

    current = second
    rerender({ id: 'b' })

    // Still loading, but the old value stays on screen rather than blanking.
    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBe('a-data')

    await act(async () => {
      second.resolve('b-data')
      await second.promise
    })
    expect(result.current.loading).toBe(false)
    expect(result.current.data).toBe('b-data')
  })
})
