import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SampleDatasetSelector } from '@/components/SampleDatasetSelector';
import { API_URL } from '@/lib/constants';
import { WorkflowStage } from '@/lib/types/workflow';

const mockCompleteStage = jest.fn();
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({ completeStage: mockCompleteStage }),
}));

// #470: the selector fetched '/api/v1/onboarding/sample-datasets' relative to the frontend origin.
const dataset = {
  dataset_id: 'customer_churn', name: 'Customer Churn', description: 'd', size_mb: 1, rows: 10, columns: 3,
  problem_type: 'binary_classification', difficulty_level: 'beginner', tags: [], preview_data: [],
  target_column: 'churn', feature_columns: ['a'], learning_objectives: [], expected_accuracy: 0.8,
};

describe('SampleDatasetSelector (#470)', () => {
  beforeEach(() => {
    global.fetch = jest.fn((url: string) => {
      const u = String(url);
      if (u.endsWith('/load')) return Promise.resolve({ ok: true, json: async () => ({ success: true, dataset_id: 'ud-1' }) });
      return Promise.resolve({ ok: true, json: async () => [dataset] });
    }) as jest.Mock;
  });

  it('lists and loads through the backend base URL with the API bearer', async () => {
    const onSelected = jest.fn();
    render(<SampleDatasetSelector onDatasetSelected={onSelected} />);
    await screen.findByText('Customer Churn');
    const [listUrl, listInit] = (global.fetch as jest.Mock).mock.calls[0];
    expect(listUrl).toBe(`${API_URL}/onboarding/sample-datasets`);
    expect(listInit.headers.Authorization).toBe('Bearer mock-token');

    // the card action selects the dataset; the detail panel then offers the load
    fireEvent.click(screen.getByRole('button', { name: /use this/i }));
    const loadButton = screen.queryByRole('button', { name: /load this dataset/i });
    if (loadButton) fireEvent.click(loadButton);
    await waitFor(() => expect(onSelected).toHaveBeenCalledWith('ud-1'));
    const loadCall = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).endsWith('/load'));
    expect(loadCall[0]).toBe(`${API_URL}/onboarding/sample-datasets/customer_churn/load`);
    expect(loadCall[1].method).toBe('POST');
    expect(loadCall[1].headers.Authorization).toBe('Bearer mock-token');
  });

  it('surfaces a failed dataset list instead of an empty grid', async () => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: false, status: 503, json: async () => ({}) })) as jest.Mock;
    render(<SampleDatasetSelector onDatasetSelected={jest.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load the sample datasets/i);
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  // #770: the quoted score is a measured quick-mode floor, and regression reports R², not accuracy.
  it('labels the measured score by what the engine reports for the problem type', async () => {
    const house = { ...dataset, dataset_id: 'house_prices', name: 'House Prices', problem_type: 'regression' };
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => [dataset, house] })) as jest.Mock;
    render(<SampleDatasetSelector onDatasetSelected={jest.fn()} />);
    await screen.findByText('House Prices');
    expect(screen.getByText(/quick-mode accuracy/i).nextSibling).toHaveTextContent('80%+');
    expect(screen.getByText(/quick-mode r²/i).nextSibling).toHaveTextContent('0.80+');
    expect(screen.queryByText(/expected accuracy/i)).not.toBeInTheDocument();
  });

  it('offers no inert "Learn More" button in the preview, even for an old docs link (#770)', async () => {
    const withDocs = { ...dataset, documentation_url: 'https://docs.narrativemodeling.ai/samples/customer-churn' };
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => [withDocs] })) as jest.Mock;
    render(<SampleDatasetSelector onDatasetSelected={jest.fn()} />);
    await screen.findByText('Customer Churn');
    fireEvent.click(screen.getByRole('button', { name: /preview/i }));
    expect(await screen.findByRole('button', { name: /load this dataset/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /learn more/i })).not.toBeInTheDocument();
  });

  // #770: /explore/{id} is gated on DATA_LOADING. An upload completes that stage; a
  // loaded sample did not, so "Use This" bounced the user back to /upload.
  it('completes the data-loading stage for the loaded sample before handing it back', async () => {
    mockCompleteStage.mockClear();
    const onSelected = jest.fn(() => expect(mockCompleteStage).toHaveBeenCalled());
    render(<SampleDatasetSelector onDatasetSelected={onSelected} />);
    await screen.findByText('Customer Churn');
    fireEvent.click(screen.getByRole('button', { name: /use this/i }));
    await waitFor(() => expect(onSelected).toHaveBeenCalledWith('ud-1'));
    expect(mockCompleteStage).toHaveBeenCalledWith(
      WorkflowStage.DATA_LOADING,
      expect.objectContaining({ datasetId: 'ud-1', filename: 'Customer Churn' }),
    );
  });
});
