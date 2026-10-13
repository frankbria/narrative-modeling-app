/**
 * @jest-environment node
 *
 * GET /api/health/ready (#756): the report, with a status code a probe can act on.
 */
import { GET } from '@/app/api/health/ready/route';
import { readiness } from '@/lib/health/readiness';

jest.mock('@/lib/health/readiness', () => ({ readiness: jest.fn() }));

const report = readiness as jest.Mock;

describe('GET /api/health/ready', () => {
  it('answers 200 with the report when every check is healthy', async () => {
    const healthy = { status: 'healthy', checks: { mongo: 'healthy', api_token: 'healthy' } };
    report.mockResolvedValue(healthy);

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(healthy);
  });

  it('answers 503, naming the failing check, when one is not', async () => {
    const broken = {
      status: 'unhealthy',
      checks: { mongo: 'unhealthy (MongoServerError AuthenticationFailed)', api_token: 'healthy' },
    };
    report.mockResolvedValue(broken);

    const response = await GET();

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual(broken);
  });
});
