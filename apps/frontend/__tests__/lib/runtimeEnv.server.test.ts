/**
 * @jest-environment node
 *
 * On the server there is no page: `publicEnv` reads the container's environment when
 * the code runs (#831).
 */
import { publicEnv } from '@/lib/runtimeEnv'

const ORIGINAL_API_URL = process.env.NEXT_PUBLIC_API_URL

afterEach(() => {
  process.env.NEXT_PUBLIC_API_URL = ORIGINAL_API_URL
})

describe('publicEnv on the server', () => {
  it('reads the process environment at call time, not at import', () => {
    process.env.NEXT_PUBLIC_API_URL = 'https://dev.example/api/v1'
    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://dev.example/api/v1')

    process.env.NEXT_PUBLIC_API_URL = 'https://www.example/api/v1'
    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBe('https://www.example/api/v1')
  })

  it.each([undefined, ''])('is undefined for %p, so a blank from compose takes the call site default', (value) => {
    if (value === undefined) delete process.env.NEXT_PUBLIC_API_URL
    else process.env.NEXT_PUBLIC_API_URL = value

    expect(publicEnv('NEXT_PUBLIC_API_URL')).toBeUndefined()
  })
})
