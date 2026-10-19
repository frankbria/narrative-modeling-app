import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeaturesPage from '@/app/features/page';
import { WorkflowStage } from '@/lib/types/workflow';
import realUserData from '@/__tests__/fixtures/userDataResponse.unprocessed.json';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn(), prefetch: jest.fn() }),
}));

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token'),
}));

jest.mock('@/lib/constants', () => ({
  API_URL: 'http://localhost:8000/api/v1',
}));

jest.mock('@/lib/hooks/useStageGuard', () => ({
  useStageGuard: () => ({ ready: true }),
}));

const mockNavigation = jest.fn();
jest.mock('@/components/workflow/StageNavigation', () => ({
  StageNavigation: (props: { ready?: boolean }) => {
    mockNavigation(props);
    return <div data-testid="stage-navigation" data-ready={String(props.ready)} />;
  },
}));

const mockCompleteStage = jest.fn();
const mockWorkflow = {
  state: {
    currentStage: WorkflowStage.FEATURE_ENGINEERING,
    completedStages: new Set<WorkflowStage>(),
    stageData: {} as Record<string, unknown>,
    datasetId: 'ds-1' as string | undefined,
  },
  completeStage: mockCompleteStage,
};
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => mockWorkflow,
}));

const mockFetch = jest.fn();

/** GET /user_data/{id} as the API answers it once the dataset has been processed. */
function userData(columns: string[]) {
  return { ...realUserData, data_schema: columns.map((field_name) => ({ field_name })) };
}

function answer(body: unknown, ok = true) {
  return { ok, status: ok ? 200 : 404, json: async () => body };
}

const COLUMNS = ['plan', 'region', 'spend', 'bought'];

beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = mockFetch as unknown as typeof fetch;
  mockWorkflow.state.datasetId = 'ds-1';
  mockWorkflow.state.stageData = {};
  mockWorkflow.state.completedStages = new Set();
  mockFetch.mockResolvedValue(answer(userData(COLUMNS)));
});

async function loaded() {
  await waitFor(() => expect(screen.getByLabelText('plan')).toBeInTheDocument());
}

describe('Feature Engineering page', () => {
  it("lists the dataset's columns, read from the route that answers for an upload's id", async () => {
    render(<FeaturesPage />);
    await loaded();

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/user_data/ds-1',
      expect.objectContaining({ headers: { Authorization: 'Bearer mock-token' } }),
    );
    for (const column of COLUMNS) expect(screen.getByLabelText(column)).toBeChecked();
    expect(screen.getByText('4 of 4 columns selected')).toBeInTheDocument();
    const called = mockFetch.mock.calls.map(([url]) => String(url));
    expect(called.filter((url) => /features\/(suggestions|generate)/.test(url))).toEqual([]);
  });

  it('records the selection and what was left out, and only then lets the user continue', async () => {
    render(<FeaturesPage />);
    await loaded();
    expect(screen.getByTestId('stage-navigation')).toHaveAttribute('data-ready', 'false');

    fireEvent.click(screen.getByLabelText('region'));
    fireEvent.click(screen.getByRole('button', { name: 'Use these 3 columns' }));

    expect(mockCompleteStage).toHaveBeenCalledWith(
      WorkflowStage.FEATURE_ENGINEERING,
      expect.objectContaining({
        selectedFeatures: ['plan', 'spend', 'bought'],
        excludedFeatures: ['region'],
      }),
    );
  });

  it('comes back to a recorded choice, and asks for it to be recorded again once it changes', async () => {
    mockWorkflow.state.completedStages = new Set([WorkflowStage.FEATURE_ENGINEERING]);
    mockWorkflow.state.stageData = {
      [WorkflowStage.FEATURE_ENGINEERING]: {
        selectedFeatures: ['plan', 'spend', 'bought'],
        excludedFeatures: ['region'],
      },
    };
    render(<FeaturesPage />);
    await loaded();

    expect(screen.getByLabelText('region')).not.toBeChecked();
    expect(screen.getByTestId('stage-navigation')).toHaveAttribute('data-ready', 'true');
    expect(screen.getByTestId('choice-recorded')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('region'));

    expect(screen.getByTestId('stage-navigation')).toHaveAttribute('data-ready', 'false');
    expect(screen.queryByTestId('choice-recorded')).not.toBeInTheDocument();
  });

  it('will not record fewer than two columns', async () => {
    render(<FeaturesPage />);
    await loaded();

    for (const column of ['plan', 'region', 'spend']) fireEvent.click(screen.getByLabelText(column));

    expect(screen.getByText('Select at least 2 columns.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Use these 1 columns' })).toBeDisabled();
  });

  describe('the interaction features switch (#974)', () => {
    const SWITCH = 'Also try interaction features';

    it('is off by default, explains itself, and is recorded with the choice', async () => {
      render(<FeaturesPage />);
      await loaded();

      const toggle = screen.getByRole('switch', { name: SWITCH });
      expect(toggle).not.toBeChecked();
      expect(screen.getByText(/lengthen training/)).toBeInTheDocument();

      fireEvent.click(toggle);
      fireEvent.click(screen.getByRole('button', { name: 'Use these 4 columns' }));

      expect(mockCompleteStage).toHaveBeenCalledWith(
        WorkflowStage.FEATURE_ENGINEERING,
        expect.objectContaining({ createInteractions: true, excludedFeatures: [] }),
      );
    });

    it('records off when it was never touched', async () => {
      render(<FeaturesPage />);
      await loaded();

      fireEvent.click(screen.getByRole('button', { name: 'Use these 4 columns' }));

      expect(mockCompleteStage).toHaveBeenCalledWith(
        WorkflowStage.FEATURE_ENGINEERING,
        expect.objectContaining({ createInteractions: false }),
      );
    });

    it('comes back on, and flipping it asks for the choice to be recorded again', async () => {
      mockWorkflow.state.completedStages = new Set([WorkflowStage.FEATURE_ENGINEERING]);
      mockWorkflow.state.stageData = {
        [WorkflowStage.FEATURE_ENGINEERING]: {
          selectedFeatures: COLUMNS,
          excludedFeatures: [],
          createInteractions: true,
        },
      };
      render(<FeaturesPage />);
      await loaded();

      expect(screen.getByRole('switch', { name: SWITCH })).toBeChecked();
      expect(screen.getByTestId('stage-navigation')).toHaveAttribute('data-ready', 'true');

      fireEvent.click(screen.getByRole('switch', { name: SWITCH }));

      expect(screen.getByRole('switch', { name: SWITCH })).not.toBeChecked();
      expect(screen.getByTestId('stage-navigation')).toHaveAttribute('data-ready', 'false');
    });

    it('starts from what was recorded when the dataset changes, not from the last dataset’s flip', async () => {
      const { rerender } = render(<FeaturesPage />);
      await loaded();
      fireEvent.click(screen.getByRole('switch', { name: SWITCH }));
      expect(screen.getByRole('switch', { name: SWITCH })).toBeChecked();

      mockWorkflow.state.datasetId = 'ds-2';
      rerender(<FeaturesPage />);
      await loaded();

      expect(screen.getByRole('switch', { name: SWITCH })).not.toBeChecked();
    });
  });

  it('says so when the columns cannot be read, and reads them again on retry', async () => {
    mockFetch.mockResolvedValue(answer({ detail: 'not found' }, false));
    render(<FeaturesPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('alert')).toHaveTextContent("could not read this dataset's columns");
    expect(screen.queryByRole('button', { name: /Use these/ })).not.toBeInTheDocument();

    mockFetch.mockResolvedValue(answer(userData(COLUMNS)));
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    await loaded();
  });

  it('says so when the request itself fails', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));
    render(<FeaturesPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  });

  it('sends a visitor with no dataset back to the upload', () => {
    mockWorkflow.state.datasetId = undefined;
    render(<FeaturesPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Go to Data Loading' }));

    expect(mockPush).toHaveBeenCalledWith('/upload');
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
