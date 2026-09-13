/**
 * HealthMonitor polls the real /health liveness endpoint and distinguishes
 * unreachable from reachable-but-unwell (#479). jest.setup makes global.fetch
 * reject by default, so every test stubs it explicitly.
 */
import { render, screen, waitFor } from '@testing-library/react';

import { HealthMonitor } from '@/components/HealthMonitor';

function stubFetch(impl: (url: string) => Promise<Response> | Response) {
  global.fetch = jest.fn((url: string) => Promise.resolve(impl(url))) as unknown as typeof fetch;
}

const API = 'http://localhost:8000/api/v1';

afterEach(() => jest.restoreAllMocks());

describe('HealthMonitor (#479)', () => {
  it('polls /health at the API origin, not a nonexistent versioned path', async () => {
    const seen: string[] = [];
    stubFetch((url) => {
      seen.push(url);
      return { ok: true, json: async () => ({ status: 'alive', environment: 'test', version: '9.9.9' }) } as Response;
    });
    render(<HealthMonitor backendUrl={API} refreshInterval={999999} />);
    await waitFor(() => expect(screen.getByTestId('health-icon-alive')).toBeInTheDocument());
    // Root /health, never /api/v1/health/status or /health/metrics.
    expect(seen).toEqual(['http://localhost:8000/health']);
    expect(screen.getByTestId('health-status-text')).toHaveTextContent('Backend reachable');
    expect(screen.getByText('Version: 9.9.9')).toBeInTheDocument();
  });

  it('a failed poll reads as unreachable, not unhealthy', async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error('network'))) as unknown as typeof fetch;
    render(<HealthMonitor backendUrl={API} refreshInterval={999999} />);
    await waitFor(() => expect(screen.getByTestId('health-icon-unreachable')).toBeInTheDocument());
    expect(screen.getByTestId('health-status-text')).toHaveTextContent('Cannot reach the backend');
  });

  it('a reached-but-erroring backend (non-2xx) is distinct from unreachable', async () => {
    stubFetch(() => ({ ok: false, status: 503, json: async () => ({}) }) as Response);
    render(<HealthMonitor backendUrl={API} refreshInterval={999999} />);
    await waitFor(() => expect(screen.getByTestId('health-icon-erroring')).toBeInTheDocument());
    expect(screen.getByTestId('health-status-text')).toHaveTextContent('reporting a problem');
  });

  it('renders no fabricated metrics grid', async () => {
    stubFetch(() => ({ ok: true, json: async () => ({ status: 'alive', environment: 'test', version: '1' }) }) as Response);
    render(<HealthMonitor backendUrl={API} refreshInterval={999999} />);
    await waitFor(() => expect(screen.getByTestId('health-icon-alive')).toBeInTheDocument());
    for (const gone of ['Memory Usage', 'API Performance', 'Security Events', 'Upload Statistics']) {
      expect(screen.queryByText(gone)).not.toBeInTheDocument();
    }
  });
});
