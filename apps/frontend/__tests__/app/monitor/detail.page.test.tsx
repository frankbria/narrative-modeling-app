import { render, screen, waitFor } from '@testing-library/react'
import ModelMonitoringPage from '@/app/monitor/[id]/page'
import { ProductionService } from '@/lib/services/production'
import { ModelService } from '@/lib/services/model'

// Issue #85: the monitor detail page surfaces deployment health, alerts and
// latency percentiles from the new monitoring endpoints.

jest.mock('next/navigation', () => ({
  useParams: () => ({ id: 'model_123' }),
}))

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { email: 'a@b.c' } } }),
}))

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok-123'),
}))

jest.mock('@/lib/services/model')
jest.mock('@/lib/services/production')

// Recharts wrappers render as passthrough divs in jsdom.
jest.mock('@/components/LineChart', () => ({
  LineChart: () => <div data-testid="line-chart" />,
}))
jest.mock('@/components/BarChart', () => ({
  BarChart: () => <div data-testid="bar-chart" />,
}))

const mockModel = ModelService as jest.Mocked<typeof ModelService>
const mockProd = ProductionService as jest.Mocked<typeof ProductionService>

beforeEach(() => {
  mockModel.getModel.mockResolvedValue({
    model_id: 'model_123',
    name: 'Churn Model',
    problem_type: 'binary_classification',
    algorithm: 'Random Forest',
    target_column: 'churn',
    cv_score: 0.85,
    test_score: 0.83,
    created_at: '2026-06-01T00:00:00',
    is_active: true,
    feature_names: ['a', 'b'],
    n_samples_train: 1000,
    n_features: 2,
  } as never)

  mockProd.getModelMetrics.mockResolvedValue({
    model_id: 'model_123',
    model_name: 'Churn Model',
    total_predictions: 100,
    error_count: 12,
    avg_latency_ms: 1200,
    latency_percentiles: { p50: 40, p90: 80, p95: 95, p99: 120 },
    predictions_per_hour: 10,
    avg_confidence: 0.9,
    error_rate: 0.12,
    time_window_hours: 24,
  })

  mockProd.getPredictionLogs.mockResolvedValue({
    model_id: 'model_123',
    logs: [],
    count: 0,
    limit: 100,
  })

  mockProd.getPredictionDistribution.mockResolvedValue({
    model_id: 'model_123',
    distribution: { yes: 60, no: 40 },
    total: 100,
    unique_values: 2,
  })

  mockProd.getUsageTimeline.mockResolvedValue({
    model_id: 'model_123',
    bucket_minutes: 60,
    time_window_hours: 24,
    buckets: [
      { timestamp: '2026-06-25T00:00:00', requests: 5, errors: 1, avg_latency_ms: 20 },
    ],
  })

  mockProd.getDeploymentHealth.mockResolvedValue({
    model_id: 'model_123',
    status: 'degraded',
    error_rate: 0.12,
    avg_latency_ms: 1200,
    requests: 100,
    last_request_at: '2026-06-25T00:00:00',
    alerts: [
      { level: 'warning', type: 'error_rate', message: 'Error rate 12.0% exceeds 5%' },
      { level: 'warning', type: 'latency', message: 'Avg latency 1200ms exceeds 1000ms' },
    ],
    time_window_hours: 24,
  })
})

afterEach(() => jest.clearAllMocks())

it('renders the deployment health badge and active alerts', async () => {
  render(<ModelMonitoringPage />)

  expect(await screen.findByText('Degraded')).toBeInTheDocument()
  const alerts = await screen.findAllByTestId('health-alert')
  expect(alerts).toHaveLength(2)
  expect(screen.getByText(/Error rate 12.0% exceeds 5%/)).toBeInTheDocument()
})

it('requests the timeline and health endpoints on load', async () => {
  render(<ModelMonitoringPage />)

  await waitFor(() => {
    expect(mockProd.getUsageTimeline).toHaveBeenCalledWith('model_123', 24, 'tok-123')
    expect(mockProd.getDeploymentHealth).toHaveBeenCalledWith('model_123', 24, 'tok-123')
  })
})
