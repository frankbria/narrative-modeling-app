import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SampleDatasetSelector } from '@/components/SampleDatasetSelector';
import { API_URL } from '@/lib/constants';

// #470: the selector fetched '/api/v1/onboarding/sample-datasets' relative to the frontend origin.
const dataset = {
  dataset_id: 'customer_churn', name: 'Customer Churn', description: 'd', size_mb: 1, rows: 10, columns: 3,
  problem_type: 'binary_classification', difficulty_level: 'beginner', tags: [], preview_data: [],
  target_column: 'churn', feature_columns: ['a'], learning_objectives: [], download_url: '/x',
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
});
