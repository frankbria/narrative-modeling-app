import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DeployPage from '@/app/deploy/page';
import { WorkflowStage } from '@/lib/types/workflow';

// Mock the router
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
}));

// Mock auth helpers
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token'),
}));

// Mock constants
jest.mock('@/lib/constants', () => ({
  API_URL: 'http://localhost:8000/api/v1',
}));

// Stage guard: always ready (access control is tested separately).
jest.mock('@/lib/hooks/useStageGuard', () => ({
  useStageGuard: () => ({ ready: true }),
}));

// StageNavigation is exercised by its own suite; stub it here.
jest.mock('@/components/workflow/StageNavigation', () => ({
  StageNavigation: () => <div data-testid="stage-navigation" />,
}));

// EndpointTester has its own suite; stub it (it would otherwise fetch features).
jest.mock('@/components/EndpointTester', () => ({
  EndpointTester: () => <div data-testid="endpoint-tester" />,
}));

// The page reads real feature names to build the example request; stub it.
jest.mock('@/lib/services/model', () => ({
  modelService: {
    getModelFeatures: jest.fn().mockResolvedValue({
      features: [{ name: 'age', type: 'number' }],
      problem_type: 'binary_classification',
      target_column: 'target',
    }),
  },
}));

const mockCompleteStage = jest.fn();
const mockRequestStageRedirect = jest.fn();

const createMockWorkflowState = (overrides = {}) => ({
  currentStage: WorkflowStage.DEPLOYMENT,
  completedStages: new Set<WorkflowStage>(),
  stageData: {} as Record<WorkflowStage, unknown>,
  datasetId: 'ds-1',
  modelId: 'model-1',
  ...overrides,
});

const mockWorkflowContext = {
  state: createMockWorkflowState(),
  completeStage: mockCompleteStage,
  requestStageRedirect: mockRequestStageRedirect,
};

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => mockWorkflowContext,
}));

const mockFetch = jest.fn();
global.fetch = mockFetch;

const DEPLOY_RESPONSE = {
  model_id: 'model-1',
  status: 'deployed',
  deployed_at: '2026-06-16T00:00:00Z',
  deployment_endpoint: 'https://api.example.com/v1/models/model-1',
  message: 'Model model-1 deployed successfully',
};

// GET /ml/{id} shape (status check on mount): not yet deployed by default.
// Deployment state lives on the MLModel record's top-level fields (#84).
const notDeployedModel = {
  model_id: 'model-1',
  status: 'trained',
  is_deployed: false,
  deployment_endpoint: null,
  deployed_at: null,
};

describe('DeployPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
    mockWorkflowContext.state = createMockWorkflowState();
  });

  describe('mount status check', () => {
    it('checks deployment status via GET /ml/{id} (the real MLModel surface)', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(notDeployedModel),
      });

      render(<DeployPage />);

      await waitFor(() => expect(mockFetch).toHaveBeenCalled());
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toBe('http://localhost:8000/api/v1/ml/model-1');
      expect(url).not.toContain('/models/');
    });

    it('shows the deployed state when the model is already deployed', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            model_id: 'model-1',
            status: 'deployed',
            is_deployed: true,
            deployment_endpoint: 'https://api.example.com/v1/models/model-1',
            deployed_at: '2026-06-16T00:00:00Z',
          }),
      });

      render(<DeployPage />);

      expect(
        await screen.findByText('Model Deployed Successfully!')
      ).toBeInTheDocument();
      expect(
        screen.getByText('https://api.example.com/v1/models/model-1')
      ).toBeInTheDocument();
    });
  });

  describe('deploy action', () => {
    beforeEach(() => {
      // First call = mount status check (not deployed), second = the PUT deploy.
      mockFetch
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(notDeployedModel) })
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(DEPLOY_RESPONSE) });
    });

    it('triggers deployment with PUT to /ml/{id}/deploy', async () => {
      render(<DeployPage />);

      const button = await screen.findByRole('button', { name: /deploy model/i });
      fireEvent.click(button);

      await waitFor(() => {
        const deployCall = mockFetch.mock.calls.find(
          ([u]) => (u as string).endsWith('/ml/model-1/deploy')
        );
        expect(deployCall).toBeDefined();
        const init = deployCall![1] as RequestInit;
        expect(init.method).toBe('PUT');
        // Backend persists `endpoint` verbatim (no default), so the UI must
        // supply the production serving URL to get a usable endpoint back.
        const body = JSON.parse(init.body as string);
        expect(body.endpoint).toBe(
          'http://localhost:8000/api/v1/production/v1/models/model-1'
        );
      });
    });

    it('renders the real deployment_endpoint and no API key section', async () => {
      render(<DeployPage />);

      fireEvent.click(await screen.findByRole('button', { name: /deploy model/i }));

      expect(
        await screen.findByText('https://api.example.com/v1/models/model-1')
      ).toBeInTheDocument();
      expect(screen.queryByText('API Key')).not.toBeInTheDocument();
    });

    it('returns to the idle state when deployment fails (non-2xx)', async () => {
      mockFetch.mockReset();
      mockFetch
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(notDeployedModel) })
        .mockResolvedValueOnce({ ok: false, status: 400, statusText: 'Bad Request', json: () => Promise.resolve({}) });

      render(<DeployPage />);

      fireEvent.click(await screen.findByRole('button', { name: /deploy model/i }));

      // Not stuck on the "Deploying Your Model" spinner; back to the deploy CTA.
      expect(
        await screen.findByRole('button', { name: /deploy model/i })
      ).toBeInTheDocument();
      expect(screen.queryByText('Deploying Your Model')).not.toBeInTheDocument();
      expect(mockCompleteStage).not.toHaveBeenCalled();
    });

    it('completes the stage with model_id and deployment_endpoint', async () => {
      render(<DeployPage />);

      fireEvent.click(await screen.findByRole('button', { name: /deploy model/i }));

      await waitFor(() => expect(mockCompleteStage).toHaveBeenCalled());
      const [stage, data] = mockCompleteStage.mock.calls[0];
      expect(stage).toBe(WorkflowStage.DEPLOYMENT);
      expect(data).toMatchObject({
        deploymentId: 'model-1',
        apiEndpoint: 'https://api.example.com/v1/models/model-1',
      });
    });
  });
});
