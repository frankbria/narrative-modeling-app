import { ProductionService } from '@/lib/services/production'

// Issue #85: deployment monitoring service methods (timeline + health).
describe('ProductionService monitoring (issue #85)', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
  })

  describe('getUsageTimeline', () => {
    it('fetches the timeline endpoint with hours + bearer token', async () => {
      const payload = {
        model_id: 'm1',
        bucket_minutes: 60,
        time_window_hours: 24,
        buckets: [
          { timestamp: '2026-06-25T00:00:00', requests: 5, errors: 1, avg_latency_ms: 20 },
        ],
      }
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(payload),
      })

      const result = await ProductionService.getUsageTimeline('m1', 24, 'tok-123')

      const [url, init] = (global.fetch as jest.Mock).mock.calls[0]
      expect(url).toContain('/monitoring/models/m1/timeline?hours=24')
      expect(init.headers['Authorization']).toBe('Bearer tok-123')
      expect(result).toEqual(payload)
    })

    it('throws on a non-ok response', async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false })
      await expect(ProductionService.getUsageTimeline('m1', 24, null)).rejects.toThrow(
        'Failed to fetch usage timeline'
      )
    })
  })

  describe('getDeploymentHealth', () => {
    it('fetches the health endpoint and returns the parsed payload', async () => {
      const payload = {
        model_id: 'm1',
        status: 'degraded',
        error_rate: 0.08,
        avg_latency_ms: 120,
        requests: 50,
        last_request_at: '2026-06-25T00:00:00',
        alerts: [{ level: 'warning', type: 'error_rate', message: 'high' }],
        time_window_hours: 24,
      }
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(payload),
      })

      const result = await ProductionService.getDeploymentHealth('m1', 24, 'tok-123')

      const [url] = (global.fetch as jest.Mock).mock.calls[0]
      expect(url).toContain('/monitoring/models/m1/health?hours=24')
      expect(result.status).toBe('degraded')
      expect(result.alerts).toHaveLength(1)
    })

    it('throws on a non-ok response', async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false })
      await expect(ProductionService.getDeploymentHealth('m1', 24, null)).rejects.toThrow(
        'Failed to fetch deployment health'
      )
    })
  })
})
