/**
 * @jest-environment node
 *
 * GET /api/health names the deployment from ENVIRONMENT, the variable compose sets
 * per host and reads when the request arrives (#831).
 */
import { GET } from '@/app/api/health/route'

const ORIGINAL_ENVIRONMENT = process.env.ENVIRONMENT

afterEach(() => {
  if (ORIGINAL_ENVIRONMENT === undefined) delete process.env.ENVIRONMENT
  else process.env.ENVIRONMENT = ORIGINAL_ENVIRONMENT
})

describe('GET /api/health', () => {
  it.each(['staging', 'production'])('reports the %s host it is running on', async (environment) => {
    process.env.ENVIRONMENT = environment

    const response = await GET()

    expect(response.status).toBe(200)
    expect(await response.json()).toMatchObject({ status: 'healthy', environment })
  })

  it('reports development where no environment is set', async () => {
    delete process.env.ENVIRONMENT

    expect(await (await GET()).json()).toMatchObject({ environment: 'development' })
  })
})
