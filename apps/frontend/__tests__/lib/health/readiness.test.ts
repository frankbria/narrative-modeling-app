/**
 * @jest-environment node
 *
 * The frontend's readiness report (#756): its Mongo credential and the secret it
 * shares with the backend. A stale value of either breaks sign-in while every page
 * still renders, and nothing probed for it.
 */
import { checkApiToken, checkMongo, readiness } from '@/lib/health/readiness';

const connect = jest.fn();
const command = jest.fn();
const close = jest.fn();
const constructed: Array<{ uri: string }> = [];

jest.mock('mongodb', () => ({
  MongoClient: jest.fn().mockImplementation((uri: string) => {
    constructed.push({ uri });
    return { connect, close, db: (name?: string) => ({ command: (c: unknown) => command(name, c) }) };
  }),
}));

class MongoServerError extends Error {
  codeName = 'AuthenticationFailed';
}

const ENV = {
  MONGODB_URI: 'mongodb://user:hunter2@cluster0.example.net',
  MONGODB_DB: 'narrative_modeling-staging',
  NEXTAUTH_SECRET: 'shared-secret',
  NEXT_PUBLIC_API_URL: 'https://app.example/api/v1',
};

const answering = (status: number) => jest.fn(async () => ({ status }) as Response);

beforeEach(() => {
  jest.clearAllMocks();
  constructed.length = 0;
  connect.mockResolvedValue(undefined);
  command.mockResolvedValue({ ok: 1 });
  close.mockResolvedValue(undefined);
});

describe('checkMongo', () => {
  it('pings the configured database over a connection of its own, and closes it', async () => {
    expect(await checkMongo(ENV)).toBe('healthy');

    expect(constructed).toEqual([{ uri: ENV.MONGODB_URI }]);
    expect(command).toHaveBeenCalledWith('narrative_modeling-staging', { ping: 1 });
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('names the kind of failure and nothing from its message', async () => {
    connect.mockRejectedValue(new MongoServerError('bad auth : authentication failed on cluster0.example.net'));

    const status = await checkMongo(ENV);

    expect(status).toBe('unhealthy (MongoServerError AuthenticationFailed)');
    expect(status).not.toMatch(/cluster0|hunter2|example\.net/);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('is unhealthy without a connection string, and opens nothing', async () => {
    expect(await checkMongo({ ...ENV, MONGODB_URI: '' })).toBe('unhealthy (MONGODB_URI is not set)');
    expect(constructed).toEqual([]);
  });
});

describe('checkApiToken', () => {
  it('sends the backend a token signed with this process\'s secret', async () => {
    const fetcher = answering(200);

    expect(await checkApiToken(ENV, fetcher)).toBe('healthy');

    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://app.example/api/v1/datasets?page=1&limit=1');
    const token = (init.headers as Record<string, string>).Authorization.replace('Bearer ', '');
    const [header, payload, signature] = token.split('.');
    const { createHmac } = jest.requireActual('node:crypto');
    expect(signature).toBe(createHmac('sha256', 'shared-secret').update(`${header}.${payload}`).digest('base64url'));
    expect(JSON.parse(Buffer.from(payload, 'base64url').toString()).sub).toBe('frontend-health-probe');
  });

  it('reads a 401 as the two halves disagreeing about the secret', async () => {
    expect(await checkApiToken(ENV, answering(401))).toBe(
      'unhealthy (the backend rejected a token signed with this NEXTAUTH_SECRET)',
    );
  });

  it('a 403 is the invite gate refusing the probe user: the signature was accepted', async () => {
    expect(await checkApiToken(ENV, answering(403))).toBe('healthy');
  });

  it('says so when the backend is failing or cannot be reached, without the error text', async () => {
    expect(await checkApiToken(ENV, answering(502))).toBe('unhealthy (the backend answered 502)');

    const refused = jest.fn(async () => {
      throw new TypeError('fetch failed: connect ECONNREFUSED 10.0.0.7:443');
    });
    expect(await checkApiToken(ENV, refused)).toBe('unhealthy (TypeError)');
  });

  it('is unhealthy when the secret or the API address is missing', async () => {
    expect(await checkApiToken({ ...ENV, NEXTAUTH_SECRET: '' }, answering(200))).toBe(
      'unhealthy (NEXTAUTH_SECRET is not set)',
    );
    expect(await checkApiToken({ ...ENV, NEXT_PUBLIC_API_URL: '' }, answering(200))).toBe(
      'unhealthy (NEXT_PUBLIC_API_URL is not set)',
    );
  });
});

describe('readiness', () => {
  it('is healthy only when every check is', async () => {
    expect(await readiness(ENV, answering(200))).toEqual({
      status: 'healthy',
      checks: { mongo: 'healthy', api_token: 'healthy' },
    });

    const broken = await readiness(ENV, answering(401));
    expect(broken.status).toBe('unhealthy');
    expect(broken.checks.mongo).toBe('healthy');
  });
});
