/**
 * Pins the URLs these modules actually request, against the backend's real route
 * table (#406).
 *
 * The bug this guards: `NEXT_PUBLIC_API_URL` is `http://…/api/v1` everywhere it is
 * set — `.env.local`, the Dockerfile dummy, `ci.yml` — but three modules assumed a
 * bare origin and re-appended the prefix, after stripping a trailing `/api` that is
 * never there. That produced `/api/v1/api/user_data/…` and even
 * `/api/v1/api/v1/upload/…`, so the AI Insights panel and chunked-upload resume
 * 404'd in production while every test stayed green.
 *
 * They stayed green because the existing suites build the expected URL with the
 * same expression as the code under test (`process.env.NEXT_PUBLIC_API_URL || …`
 * plus the same suffix), so any prefix mistake cancels out on both sides. The
 * assertions below hardcode the **path the FastAPI app actually serves**, which is
 * the only version of this test that can fail.
 */
import { HistoryService } from '@/lib/services/history'

/** Routes verified against GET /api/v1/openapi.json on 2026-08-02. */
const BASE = 'https://api.example.test/api/v1'

/** The single fetch call a test made, as a string. */
function requestedUrl(mock: jest.Mock, call = 0): string {
  const arg = mock.mock.calls[call][0]
  return typeof arg === 'string' ? arg : arg.url
}

const ok = (body: unknown = {}) => ({
  ok: true,
  status: 200,
  json: jest.fn().mockResolvedValue(body),
})

describe('API URL construction (#406)', () => {
  const ORIGINAL = process.env.NEXT_PUBLIC_API_URL

  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_URL = BASE
    jest.resetModules()
    global.fetch = jest.fn().mockResolvedValue(ok())
  })

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = ORIGINAL
    jest.resetAllMocks()
  })

  // Every asserted path is a literal from the backend's route table. If a module
  // double-prefixes, the string simply will not match.
  it.each([
    ['undo', (s: HistoryService) => s.undo('ds-1', 'tok'), '/api/v1/transformations/datasets/ds-1/history/undo'],
    ['redo', (s: HistoryService) => s.redo('ds-1', 'tok'), '/api/v1/transformations/datasets/ds-1/history/redo'],
    ['getHistory', (s: HistoryService) => s.getHistory('ds-1', 'tok'), '/api/v1/transformations/datasets/ds-1/history'],
  ])('HistoryService.%s requests the real route', async (_name, call, expected) => {
    const { HistoryService: Svc } = await import('@/lib/services/history')
    await call(new Svc() as HistoryService).catch(() => {})

    const url = requestedUrl(global.fetch as jest.Mock)
    expect(url).toContain(expected)
    // The failure mode is an extra prefix, so assert the negative directly:
    // `/api/v1/api/v1/…` and `/api/v1/api/…` both satisfy `toContain` above
    // only if the suffix still lines up — this is what actually pins it.
    expect(url).toBe(`${BASE}${expected.replace('/api/v1', '')}`)
  })

  it('useChunkedUpload resume targets /upload/chunked/{id}/resume exactly once-prefixed', async () => {
    // The resume path is the one chunked-upload site that derived its own base;
    // its three siblings (init/chunk/complete) already used NEXT_PUBLIC_API_URL
    // directly, which is what made the inconsistency easy to miss.
    const src = await import('fs').then((fs) =>
      fs.readFileSync(
        require.resolve('@/lib/hooks/useChunkedUpload'),
        'utf8'
      )
    )

    // No `/api/v1` or `/api/` literal may appear in a template URL: the base
    // already carries the prefix.
    const templatedPaths = [...src.matchAll(/fetch\(\s*`\$\{[A-Za-z]+\}([^`]*)`/g)].map(
      (m) => m[1]
    )
    expect(templatedPaths.length).toBeGreaterThan(0)
    for (const path of templatedPaths) {
      expect(path).not.toMatch(/^\/api(\/|$)/)
    }
    expect(templatedPaths).toContain('/upload/chunked/${sessionId}/resume')
  })

  it('useDatasetChatContext does not re-append /api to the versioned base', async () => {
    const src = await import('fs').then((fs) =>
      fs.readFileSync(
        require.resolve('@/lib/hooks/useDatasetChatContext'),
        'utf8'
      )
    )

    const templatedPaths = [...src.matchAll(/fetch\(\s*`\$\{[A-Za-z]+\}([^`]*)`/g)].map(
      (m) => m[1]
    )
    expect(templatedPaths.length).toBeGreaterThan(0)
    for (const path of templatedPaths) {
      expect(path).not.toMatch(/^\/api(\/|$)/)
    }
    // And the strip that made the old code look deliberate is gone for good.
    expect(src).not.toMatch(/replace\(\s*\/\\\/api\$\//)
  })
})
