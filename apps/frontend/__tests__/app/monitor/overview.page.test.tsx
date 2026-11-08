import { render, screen, fireEvent, within } from '@testing-library/react'
import MonitoringPage from '@/app/monitor/page'
import { ProductionService, type UsageStats } from '@/lib/services/production'

// Issue #1175: model rows are named by what they predict, latency needs
// predictions, "active" means "answered predictions", and the list pages.

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'u1' } } }),
}))
jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: async () => 't' }))
jest.mock('@/lib/services/production')

const mockProd = ProductionService as jest.Mocked<typeof ProductionService>

const model = (i: number, predictions = 0, latency = 0): UsageStats['models'][number] => ({
  model_id: `m${i}`,
  name: `model_${i}`,
  algorithm: 'XGBoost',
  target_column: `target${i}`,
  dataset_name: 'customers.csv',
  created_at: '2026-11-08T10:00:00Z',
  is_active: true,
  predictions_24h: predictions,
  avg_latency_ms: latency,
})

function load(models: UsageStats['models']) {
  mockProd.getUsageOverview.mockResolvedValue({
    total_models: models.length,
    active_models: models.length,
    total_predictions_24h: 0,
    total_api_keys: 0,
    active_api_keys: 0,
    models,
  })
  mockProd.getAPIKeyUsage.mockResolvedValue([])
}

afterEach(() => jest.clearAllMocks())

it('names rows by target, algorithm, dataset and date, never an id', async () => {
  load([model(1, 5, 20)])
  render(<MonitoringPage />)
  expect(await screen.findByText('target1 · XGBoost')).toBeInTheDocument()
  expect(screen.getByText(/customers\.csv · /)).toBeInTheDocument()
  expect(screen.queryByText('m1')).not.toBeInTheDocument()
})

it('shows no latency and counts no active models when nothing was predicted', async () => {
  load([model(1), model(2)])
  render(<MonitoringPage />)
  expect(await screen.findByText('0 received predictions')).toBeInTheDocument()
  expect(screen.queryByText('<1ms')).not.toBeInTheDocument()
  expect(screen.getAllByText('—').length).toBeGreaterThan(0)
})

it('shows the real latency once predictions exist', async () => {
  load([model(1, 4, 250)])
  render(<MonitoringPage />)
  expect(await screen.findAllByText('250ms')).toHaveLength(2)
  expect(screen.getByText('1 received predictions')).toBeInTheDocument()
})

it('pages a long model list', async () => {
  load(Array.from({ length: 12 }, (_, i) => model(i)))
  render(<MonitoringPage />)
  await screen.findByText('target0 · XGBoost')
  const body = () => screen.getAllByRole('row').length - 1
  expect(body()).toBe(10)
  fireEvent.click(screen.getByRole('button', { name: /Show more \(2 left\)/ }))
  expect(body()).toBe(12)
  expect(screen.queryByRole('button', { name: /Show more/ })).not.toBeInTheDocument()
})

it('says so when there are no models', async () => {
  load([])
  render(<MonitoringPage />)
  const empty = await screen.findByText('You have no trained models yet.')
  expect(within(empty.parentElement as HTMLElement).queryByRole('table')).toBeNull()
})
