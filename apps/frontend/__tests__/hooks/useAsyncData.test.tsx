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

describe('a result that lands after an effect cleanup (#411)', () => {
  // React StrictMode double-invokes effects in dev: mount -> effect A -> cleanup A
  // -> effect B. The old code used a closure `cancelled` flag, so A's result was
  // thrown away even though its deps were still current. When the request is slow
  // enough that only one of the two ever comes back, `loading` stays true forever.
  //
  // Observed on the AI Insights panel against a real backend: two requests, one
  // HTTP 200 at 35s, and "Generating AI insights…" still on screen at 240s.
  //
  // Discarding by closure flag is also redundant — `settled` already ignores any
  // result whose deps or reload token no longer match. What it cannot do is
  // recover a result the effect threw away.

  it('accepts an in-flight result whose deps are current again', async () => {
    // Same shape as the StrictMode double-invoke, reachable without it: the effect
    // for 'a' is cleaned up when deps move to 'b', then deps come back to 'a' (tab
    // away and back) while that first request is still in flight. Its result is
    // valid for the current deps, but the closure flag threw it away — so nothing
    // ever settled and the spinner stayed up.
    const releases: ((v: string) => void)[] = []
    const loader = jest.fn(
      () => new Promise<string>((res) => { releases.push(res) })
    )

    const { result, rerender } = renderHook(
      ({ id }) => useAsyncData(loader, [id]),
      { initialProps: { id: 'a' } }
    )

    rerender({ id: 'b' })
    rerender({ id: 'a' })

    expect(result.current.loading).toBe(true)

    await act(async () => {
      releases[0]('answer for a')   // the request the cleanup discarded
      await Promise.resolve()
    })

    expect(result.current.data).toBe('answer for a')
    expect(result.current.loading).toBe(false)
  })

  it('still ignores a result whose deps have moved on', async () => {
    // The protection the closure flag was there for must survive: a slow request
    // for 'a' must not populate the hook after the caller has switched to 'b'.
    const pending: Record<string, (v: string) => void> = {}
    const loader = jest.fn(function (this: void) {
      return new Promise<string>((res) => {
        pending[Object.keys(pending).length === 0 ? 'first' : 'second'] = res
      })
    })

    const { result, rerender } = renderHook(
      ({ id }) => useAsyncData(loader, [id]),
      { initialProps: { id: 'a' } }
    )

    rerender({ id: 'b' })

    await act(async () => {
      pending.first('stale answer for a')
      await Promise.resolve()
    })

    expect(result.current.data).toBeUndefined()
    expect(result.current.loading).toBe(true)

    await act(async () => {
      pending.second('fresh answer for b')
      await Promise.resolve()
    })

    expect(result.current.data).toBe('fresh answer for b')
    expect(result.current.loading).toBe(false)
  })
})

describe('disabling mid-flight (#417 review)', () => {
  // Before #411 this was covered by accident: `enabled` was in the fetch effect's
  // dependency array, so flipping it re-ran the effect and the OLD instance's
  // cleanup set `cancelled = true`. Removing that cleanup removed the protection
  // with it — `stillWanted()` checked mounted/token/deps but not `enabled`, and
  // `settled` does not check it either, so a request begun while enabled would
  // still populate `data` after the caller had gated the fetch off.
  it('does not record a result that resolves after enabled goes false', async () => {
    let release: (v: string) => void = () => {}
    const loader = jest.fn(() => new Promise<string>((res) => { release = res }))

    const { result, rerender } = renderHook(
      ({ enabled }) => useAsyncData(loader, ['a'], { enabled }),
      { initialProps: { enabled: true } }
    )

    expect(loader).toHaveBeenCalledTimes(1)

    rerender({ enabled: false })

    await act(async () => {
      release('answer nobody asked for any more')
      await Promise.resolve()
    })

    expect(result.current.data).toBeUndefined()
    expect(result.current.loading).toBe(false)
  })

  it('still resolves normally when enabled stays true', async () => {
    let release: (v: string) => void = () => {}
    const loader = jest.fn(() => new Promise<string>((res) => { release = res }))

    const { result } = renderHook(() => useAsyncData(loader, ['a'], { enabled: true }))

    await act(async () => {
      release('wanted')
      await Promise.resolve()
    })

    expect(result.current.data).toBe('wanted')
  })
})

describe('two in-flight requests for the same key (#418 review)', () => {
  // Toggling `enabled` off and on with unchanged deps starts a SECOND request
  // without invalidating the first: the effect re-runs (enabled is in its dep
  // array) but there is no cleanup, so both are live. Both satisfy
  // mounted/enabled/token/deps at resolution, so whichever lands LAST wins — and
  // if that is the older request, it overwrites fresher data with staler data.
  it('an older in-flight result does not overwrite a newer one that already landed', async () => {
    const releases: ((v: string) => void)[] = []
    const loader = jest.fn(() => new Promise<string>((res) => { releases.push(res) }))

    const { result, rerender } = renderHook(
      ({ enabled }) => useAsyncData(loader, ['a'], { enabled }),
      { initialProps: { enabled: true } }
    )

    rerender({ enabled: false })
    rerender({ enabled: true })

    expect(loader).toHaveBeenCalledTimes(2)

    // The newer request answers first…
    await act(async () => {
      releases[1]('fresh')
      await Promise.resolve()
    })
    expect(result.current.data).toBe('fresh')

    // …and the older one, landing later, must not clobber it.
    await act(async () => {
      releases[0]('stale')
      await Promise.resolve()
    })
    expect(result.current.data).toBe('fresh')
  })

  it('an older result still settles when nothing newer has landed', async () => {
    // The #411 guarantee must survive: if the newest request never comes back,
    // an older one whose key is still current is better than spinning forever.
    const releases: ((v: string) => void)[] = []
    const loader = jest.fn(() => new Promise<string>((res) => { releases.push(res) }))

    const { result, rerender } = renderHook(
      ({ enabled }) => useAsyncData(loader, ['a'], { enabled }),
      { initialProps: { enabled: true } }
    )
    rerender({ enabled: false })
    rerender({ enabled: true })

    await act(async () => {
      releases[0]('the only answer that came back')
      await Promise.resolve()
    })

    expect(result.current.data).toBe('the only answer that came back')
    expect(result.current.loading).toBe(false)
  })
})

describe('ordering must be per-key, not global (#418 review round 2)', () => {
  // A single global counter reintroduces #411 via an unrelated key: a fast request
  // for B bumps the counter past a slow, still-valid request for A, so when A
  // finally answers it is discarded even though nothing newer FOR A has landed.
  it('a slow result is still accepted after a different key resolved ahead of it', async () => {
    const byKey: Record<string, ((v: string) => void)[]> = { A: [], B: [] }
    const loader = jest.fn(function (this: void) {
      return new Promise<string>((res) => {
        // Route by whichever key the current render asked for.
        byKey[currentKey].push(res)
      })
    })
    let currentKey: 'A' | 'B' = 'A'

    const { result, rerender } = renderHook(({ k }) => useAsyncData(loader, [k]), {
      initialProps: { k: 'A' as 'A' | 'B' },
    })

    currentKey = 'B'
    rerender({ k: 'B' })

    // B answers quickly and records.
    await act(async () => {
      byKey.B[0]('B answer')
      await Promise.resolve()
    })
    expect(result.current.data).toBe('B answer')

    // Back to A ("tab away and back"). A third request starts and never answers.
    currentKey = 'A'
    rerender({ k: 'A' })

    // The ORIGINAL slow A request finally lands. Nothing newer for A has landed,
    // so it must settle rather than leave the panel spinning.
    await act(async () => {
      byKey.A[0]('A answer, late but still correct')
      await Promise.resolve()
    })

    expect(result.current.data).toBe('A answer, late but still correct')
    expect(result.current.loading).toBe(false)
  })
})

describe('an older answer shown while a newer one is still pending (#418 review round 3)', () => {
  // This is INTENDED, not a leak, and it is the whole point of #411: given a valid
  // answer for the key the caller is currently asking about, show it rather than
  // spin. The newer answer replaces it when it arrives. Asserted here so the
  // behaviour is a decision on the record rather than a side effect of the
  // ordering rule — the reviewer on #418 rightly noted nothing pinned it.
  it('renders the older result, then replaces it when the newer one lands', async () => {
    const releases: ((v: string) => void)[] = []
    const loader = jest.fn(() => new Promise<string>((res) => { releases.push(res) }))

    const { result, rerender } = renderHook(
      ({ enabled }) => useAsyncData(loader, ['a'], { enabled }),
      { initialProps: { enabled: true } }
    )
    rerender({ enabled: false })
    rerender({ enabled: true })
    expect(loader).toHaveBeenCalledTimes(2)

    // Older answers first, while the newer is still in flight.
    await act(async () => {
      releases[0]('older but valid')
      await Promise.resolve()
    })
    expect(result.current.data).toBe('older but valid')
    expect(result.current.loading).toBe(false)

    // Newer lands and supersedes it.
    await act(async () => {
      releases[1]('newer')
      await Promise.resolve()
    })
    expect(result.current.data).toBe('newer')
  })
})
