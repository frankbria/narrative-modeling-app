/**
 * Unit tests for the predict page (issue #268).
 *
 * The 611-line prediction UI (#82/#83/#80 enrichment) previously had ZERO
 * tests, so its stage gating and the confidence / interval / contribution
 * enrichment panels could regress silently. These tests mock the model service
 * and workflow context and assert each enrichment path renders from real
 * response shapes.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PredictPage from '@/app/predict/page';
import { modelService } from '@/lib/services/model';
import { WorkflowStage } from '@/lib/types/workflow';

// ---- Controllable mocks ----
let mockSession: { data: unknown } = { data: { user: { id: 'u1' } } };
jest.mock('next-auth/react', () => ({
  useSession: () => mockSession,
}));

let mockReady = true;
jest.mock('@/lib/hooks/useStageGuard', () => ({
  useStageGuard: () => ({ ready: mockReady }),
}));

const completeStage = jest.fn();
const requestStageRedirect = jest.fn();
let mockWorkflowState: Record<string, unknown> = {
  modelId: 'model-1',
  completedStages: new Set<WorkflowStage>(),
};
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({
    state: mockWorkflowState,
    completeStage,
    requestStageRedirect,
  }),
}));

jest.mock('@/components/workflow/StageNavigation', () => ({
  StageNavigation: () => <div data-testid="stage-navigation" />,
}));

jest.mock('@/lib/services/model', () => ({
  modelService: {
    getModelFeatures: jest.fn(),
    predict: jest.fn(),
    createBatchJob: jest.fn(),
    getBatchJob: jest.fn(),
    getBatchJobProgress: jest.fn(),
    downloadBatchResults: jest.fn(),
  },
}));

const svc = modelService as jest.Mocked<typeof modelService>;

const FEATURES = {
  features: [
    { name: 'age', type: 'number' },
    { name: 'city', type: 'categorical', options: ['NYC', 'LA'] },
  ],
  class_labels: ['no', 'yes'],
  problem_type: 'classification',
  target_column: 'churn',
};

// Base single-prediction response (#82) — enrichment fields added per test.
const basePredictResponse = {
  predictions: ['yes'],
  probabilities: [[0.2, 0.8]],
  confidence: [0.8],
  class_labels: ['no', 'yes'],
  feature_names: ['age', 'city'],
  model_info: { model_id: 'model-1', algorithm: 'rf', problem_type: 'classification', target_column: 'churn' },
};

beforeEach(() => {
  jest.clearAllMocks();
  mockSession = { data: { user: { id: 'u1' } } };
  mockReady = true;
  mockWorkflowState = { modelId: 'model-1', completedStages: new Set<WorkflowStage>() };
  svc.getModelFeatures.mockResolvedValue(FEATURES as any);
});

// Render, wait for the feature form, and fill the required numeric input so the
// form is valid and the Make Prediction button is enabled.
async function renderReadyForm() {
  render(<PredictPage />);
  await screen.findByLabelText('age');
  fireEvent.change(screen.getByLabelText('age'), { target: { value: '42' } });
}

describe('PredictPage — gating', () => {
  it('shows a login prompt when there is no session', () => {
    mockSession = { data: null };
    render(<PredictPage />);
    expect(screen.getByText('Please log in to access this page.')).toBeInTheDocument();
    // The form/enrichment UI is not rendered without a session.
    expect(screen.queryByTestId('make-prediction')).not.toBeInTheDocument();
  });

  it('redirects to MODEL_TRAINING when the stage is ready but no model is trained', async () => {
    mockWorkflowState = { modelId: undefined, completedStages: new Set() };
    render(<PredictPage />);
    await waitFor(() =>
      expect(requestStageRedirect).toHaveBeenCalledWith(
        WorkflowStage.MODEL_TRAINING,
        expect.stringMatching(/train a model/i)
      )
    );
    expect(svc.getModelFeatures).not.toHaveBeenCalled();
  });

  it('does not load features until the stage guard reports ready', () => {
    mockReady = false;
    render(<PredictPage />);
    expect(svc.getModelFeatures).not.toHaveBeenCalled();
  });

  it('loads and renders the auto-generated feature form when ready with a model', async () => {
    render(<PredictPage />);
    expect(await screen.findByLabelText('age')).toBeInTheDocument();
    expect(screen.getByLabelText('city')).toBeInTheDocument();
    expect(svc.getModelFeatures).toHaveBeenCalledWith('model-1');
  });

  it('surfaces a feature-load failure as an error', async () => {
    svc.getModelFeatures.mockRejectedValueOnce(new Error('features boom'));
    render(<PredictPage />);
    expect(await screen.findByTestId('prediction-error')).toHaveTextContent('features boom');
  });
});

describe('PredictPage — single prediction result', () => {
  it('renders prediction value, confidence, and class probabilities', async () => {
    svc.predict.mockResolvedValue(basePredictResponse as any);
    await renderReadyForm();

    fireEvent.click(screen.getByTestId('make-prediction'));

    expect(await screen.findByTestId('prediction-result')).toBeInTheDocument();
    expect(screen.getByTestId('prediction-value')).toHaveTextContent('yes');
    expect(screen.getByTestId('confidence-score')).toHaveTextContent('80.0%');
    // Class probabilities labelled by class name (both classes listed).
    expect(screen.getByText('yes:')).toBeInTheDocument();
    expect(screen.getByText('no:')).toBeInTheDocument();
    // A prediction marks the stage complete.
    expect(completeStage).toHaveBeenCalledWith(WorkflowStage.PREDICTION, expect.any(Object));
  });

  it('sends include_explanations so the backend returns contributions', async () => {
    svc.predict.mockResolvedValue(basePredictResponse as any);
    await renderReadyForm();
    fireEvent.click(screen.getByTestId('make-prediction'));

    await waitFor(() => expect(svc.predict).toHaveBeenCalled());
    expect(svc.predict).toHaveBeenCalledWith(
      'model-1',
      expect.objectContaining({ include_explanations: true, data: [{ age: 42, city: 'NYC' }] })
    );
  });

  it('surfaces a prediction failure as an error and marks no stage complete', async () => {
    svc.predict.mockRejectedValueOnce(new Error('predict boom'));
    await renderReadyForm();
    fireEvent.click(screen.getByTestId('make-prediction'));

    expect(await screen.findByTestId('prediction-error')).toHaveTextContent('predict boom');
    expect(completeStage).not.toHaveBeenCalled();
  });
});

describe('PredictPage — enrichment panels (#83)', () => {
  it('shows the low-confidence warning with the threshold when flagged', async () => {
    svc.predict.mockResolvedValue({
      ...basePredictResponse,
      confidence: [0.55],
      low_confidence: [true],
      confidence_threshold: 0.7,
    } as any);
    await renderReadyForm();
    fireEvent.click(screen.getByTestId('make-prediction'));

    const warning = await screen.findByTestId('low-confidence-warning');
    expect(warning).toHaveTextContent(/low confidence/i);
    expect(warning).toHaveTextContent('70%');
  });

  it('does NOT show the low-confidence warning for a confident prediction', async () => {
    svc.predict.mockResolvedValue({ ...basePredictResponse, low_confidence: [false] } as any);
    await renderReadyForm();
    fireEvent.click(screen.getByTestId('make-prediction'));

    await screen.findByTestId('prediction-result');
    expect(screen.queryByTestId('low-confidence-warning')).not.toBeInTheDocument();
  });

  it('renders the regression prediction interval', async () => {
    svc.predict.mockResolvedValue({
      predictions: [3.14],
      confidence: undefined,
      prediction_intervals: [[1.2, 3.4]],
      feature_names: ['age', 'city'],
      model_info: { model_id: 'model-1', algorithm: 'rf', problem_type: 'regression', target_column: 'y' },
    } as any);
    await renderReadyForm();
    fireEvent.click(screen.getByTestId('make-prediction'));

    expect(await screen.findByTestId('prediction-interval')).toHaveTextContent('1.20 – 3.40');
  });

  it('renders the feature-contribution panel with signed contributions', async () => {
    svc.predict.mockResolvedValue({
      ...basePredictResponse,
      explanations: [
        {
          explanation_text: 'age pushed the prediction toward yes',
          method: 'tree_importance',
          top_features: [
            { feature_name: 'age', contribution: 0.42 },
            { feature_name: 'city', contribution: -0.13 },
          ],
        },
      ],
    } as any);
    await renderReadyForm();
    fireEvent.click(screen.getByTestId('make-prediction'));

    const panel = await screen.findByTestId('prediction-explanation');
    expect(panel).toHaveTextContent('age pushed the prediction toward yes');
    expect(panel).toHaveTextContent('age');
    expect(panel).toHaveTextContent('+0.420'); // positive contribution keeps a + sign
    expect(panel).toHaveTextContent('-0.130'); // negative contribution
  });
});

describe('PredictPage — touched-based validation (issue #282)', () => {
  it('shows no field errors on a pristine form', async () => {
    render(<PredictPage />);
    await screen.findByLabelText('age');
    expect(screen.queryByTestId('field-error-age')).not.toBeInTheDocument();
    const age = screen.getByLabelText('age');
    expect(age).not.toHaveAttribute('aria-invalid');
  });

  it('surfaces the error only after the field is blurred, wired via aria-describedby', async () => {
    render(<PredictPage />);
    const age = await screen.findByLabelText('age');

    fireEvent.blur(age);

    const err = await screen.findByTestId('field-error-age');
    expect(err).toHaveTextContent('Required');
    expect(err).toHaveAttribute('role', 'alert');
    expect(err).toHaveAttribute('id', 'field-error-age');
    expect(age).toHaveAttribute('aria-invalid', 'true');
    expect(age).toHaveAttribute('aria-describedby', 'field-error-age');
  });

  it('keeps the submit button disabled until every required field is valid', async () => {
    render(<PredictPage />);
    const age = await screen.findByLabelText('age');
    expect(screen.getByTestId('make-prediction')).toBeDisabled();

    fireEvent.change(age, { target: { value: '42' } });
    expect(screen.getByTestId('make-prediction')).toBeEnabled();
  });
});
