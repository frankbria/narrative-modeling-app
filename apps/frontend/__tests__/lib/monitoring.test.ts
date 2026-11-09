import { latencyVerdict } from '@/lib/monitoring'

describe('latencyVerdict (#1188)', () => {
  it('has nothing to say about a model that has made no predictions', () => {
    expect(latencyVerdict(0, 0)).toBeUndefined()
  })

  it.each([
    [40, 'Excellent Performance'],
    [250, 'Good Performance'],
    [1200, 'Consider Optimization'],
  ])('judges %ims as %s once there are predictions', (ms, label) => {
    expect(latencyVerdict(ms, 10)?.label).toBe(label)
  })
})
