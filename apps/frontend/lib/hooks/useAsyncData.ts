import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'

/**
 * Keyed async loading with a derived `loading` flag (#393).
 *
 * ## Why this exists
 *
 * The app had 46 copies of this shape:
 *
 * ```ts
 * const load = async () => {
 *   setLoading(true)        // synchronous setState inside an effect
 *   setError(null)
 *   const d = await svc.get(id)
 *   setData(d)
 * }
 * useEffect(() => { load() }, [id])
 * ```
 *
 * `react-hooks/set-state-in-effect` is right to flag it: render → effect →
 * `setLoading(true)` → render is a cascading render on every mount and refetch.
 *
 * The naive fix — delete `setLoading(true)` and rely on `useState(true)` — passes
 * lint and quietly removes the spinner on every *refetch*, since the initial value
 * only covers mount. That regression is invisible to a test suite that asserts on
 * resolved states.
 *
 * ## How it avoids both
 *
 * `loading` is **derived during render**, never assigned in an effect. Each result
 * records the deps it was fetched for, and a request is outstanding exactly while
 * the recorded deps do not match the current ones:
 *
 * ```
 * loading = enabled && !(resolved matches current deps)
 * ```
 *
 * So a dep change makes `loading` true in the same render that changed it, with no
 * state update at all. The effect only ever sets state from inside the promise
 * continuation, which the rule permits.
 */
export interface UseAsyncDataOptions {
  /** Skip the request while false. Mirrors the `if (session && id)` guards at call sites. */
  enabled?: boolean
  /** Shown instead of the thrown error's message. Call sites usually want fixed copy. */
  errorMessage?: string
  /**
   * Keep the last successful result visible while a new key loads, instead of
   * dropping to `undefined`.
   *
   * Off by default because it is not universally safe: showing the previous
   * dataset's numbers under a new dataset's heading is worse than showing nothing,
   * which is why some call sites explicitly cleared their state before loading.
   * Opt in where the old code kept rendering data under a spinner (a "Regenerate"
   * button that should not blank the panel it sits in).
   */
  keepPreviousData?: boolean
}

export interface UseAsyncDataResult<T> {
  data: T | undefined
  loading: boolean
  error: string | null
  /** Refetch with the current loader closure. Sets `loading` immediately. */
  reload: () => void
}

interface Resolved<T> {
  /** The deps snapshot this result was fetched for. */
  deps: DependencyList
  token: number
  data?: T
  error?: string
}

/** Shallow Object.is comparison, the same identity rule React uses for hook deps. */
function sameDeps(a: DependencyList, b: DependencyList): boolean {
  if (a.length !== b.length) return false
  return a.every((v, i) => Object.is(v, b[i]))
}

export function useAsyncData<T>(
  loader: () => Promise<T>,
  deps: DependencyList,
  options: UseAsyncDataOptions = {},
): UseAsyncDataResult<T> {
  const { enabled = true, errorMessage, keepPreviousData = false } = options

  const [reloadToken, setReloadToken] = useState(0)
  const [resolved, setResolved] = useState<Resolved<T> | null>(null)

  // Only an UNMOUNT stops a result being recorded — not an effect cleanup.
  //
  // The effect cleanup used to set a closure `cancelled` flag, which threw away a
  // result even when its deps were still current. That is what React StrictMode's
  // mount -> cleanup -> mount does on every dev mount, and what a dep round-trip
  // (a -> b -> a, e.g. tab away and back) does in production. If the surviving
  // request was slow, NOTHING ever settled: measured at 240s+ of "Generating AI
  // insights…" against a real backend that had already answered (#411).
  //
  // Discarding was never needed for correctness. Staleness is handled at read
  // time: `settled` below ignores any result whose deps or reload token no longer
  // match, so a late answer for the wrong key cannot surface. Recording it is
  // harmless; throwing it away is not recoverable.
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  // What the caller is asking for RIGHT NOW, readable from inside a promise
  // continuation. A result is recorded only if it still answers that question —
  // which keeps a slow response for 'a' from overwriting a fresh one for 'b',
  // the protection the closure flag did provide, while no longer throwing away a
  // result whose key is still current.
  // Synced in an effect, not during render: `react-hooks/refs` (enforced as an
  // error here) forbids touching a ref while rendering. An effect with no dep
  // array runs after every render, which is early enough — promise continuations
  // are always later still.
  const current = useRef({ deps, reloadToken })
  useEffect(() => {
    current.current = { deps, reloadToken }
  })

  // `loader` is deliberately NOT a dependency. Call sites pass an inline arrow, so
  // it has a new identity every render and keying on it would refetch forever.
  // Omitting it is safe rather than stale: the effect is recreated whenever
  // `requestKey` changes, so the closure it captures is always from the render that
  // requested the fetch. (An earlier draft held `loader` in a ref for this; a
  // mutation check showed the ref changed no behaviour, so it is gone.)
  useEffect(() => {
    if (!enabled) return

    const stillWanted = () =>
      mounted.current &&
      current.current.reloadToken === reloadToken &&
      sameDeps(current.current.deps, deps)

    loader()
      .then((data) => {
        if (stillWanted()) setResolved({ deps, token: reloadToken, data })
      })
      .catch((err: unknown) => {
        if (!stillWanted()) return
        setResolved({
          deps,
          token: reloadToken,
          error: errorMessage ?? (err instanceof Error ? err.message : String(err)),
        })
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps -- caller's deps, spread by contract; loader intentionally excluded
  }, [...deps, reloadToken, enabled, errorMessage])

  const reload = useCallback(() => {
    setReloadToken((t) => t + 1)
  }, [])

  const settled =
    resolved && resolved.token === reloadToken && sameDeps(resolved.deps, deps) ? resolved : null

  return {
    // With keepPreviousData, fall back to the previous key's result while the new
    // one is in flight. `loading` is unaffected, so callers can still show a spinner.
    data: settled ? settled.data : keepPreviousData ? resolved?.data : undefined,
    loading: enabled && !settled,
    error: settled?.error ?? null,
    reload,
  }
}
