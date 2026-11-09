import { latencyVerdict } from '@/lib/monitoring'

describe('latencyVerdict (#1188)', () => {
  it('has nothing to say about a model that has made no predictions', () => {
    expect(latencyVerdict(0, 0)).toBeUndefined()
  })

  it.each([
    [99, 'Excellent Performance'],
    [100, 'Good Performance'],
    [499, 'Good Performance'],
    [500, 'Consider Optimization'],
  ])('judges %ims as %s once there are predictions', (ms, label) => {
    expect(latencyVerdict(ms, 10)?.label).toBe(label)
  })
})
