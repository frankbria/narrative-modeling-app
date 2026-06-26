import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EndpointTester } from '@/components/EndpointTester';

const mockGetModelFeatures = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    getModelFeatures: (...args: unknown[]) => mockGetModelFeatures(...args),
  },
}));

const mockFetch = jest.fn();
global.fetch = mockFetch;

const ENDPOINT = 'http://localhost:8000/api/v1/production/v1/models/model-1';

describe('EndpointTester', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
    mockGetModelFeatures.mockResolvedValue({
      features: [{ name: 'age', type: 'number' }],
      problem_type: 'binary_classification',
      target_column: 'target',
    });
  });

  it('loads and renders the model input schema', async () => {
    render(<EndpointTester modelId="model-1" endpoint={ENDPOINT} />);
    expect(await screen.findByLabelText('age')).toBeInTheDocument();
    expect(mockGetModelFeatures).toHaveBeenCalledWith('model-1');
  });

  it('requires an API key before calling the endpoint', async () => {
    render(<EndpointTester modelId="model-1" endpoint={ENDPOINT} />);
    await screen.findByLabelText('age');

    fireEvent.click(screen.getByTestId('run-endpoint-test'));

    expect(await screen.findByTestId('endpoint-tester-error')).toHaveTextContent(
      /Enter an API key/i
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('POSTs to {endpoint}/predict with the X-API-Key header and renders the prediction', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ predictions: ['yes'], confidence: [0.91] }),
    });

    render(<EndpointTester modelId="model-1" endpoint={ENDPOINT} />);
    await screen.findByLabelText('age');

    fireEvent.change(screen.getByLabelText('API Key'), {
      target: { value: 'sk_live_abc' },
    });
    fireEvent.change(screen.getByLabelText('age'), { target: { value: '42' } });
    fireEvent.click(screen.getByTestId('run-endpoint-test'));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${ENDPOINT}/predict`);
    expect((init as RequestInit).method).toBe('POST');
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers['X-API-Key']).toBe('sk_live_abc');
    // Numeric inputs are coerced to numbers in the request body.
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.data[0].age).toBe(42);

    expect(await screen.findByTestId('endpoint-tester-result')).toHaveTextContent('yes');
    expect(screen.getByTestId('endpoint-tester-result')).toHaveTextContent('91.0%');
  });

  it('surfaces a server error', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      text: () => Promise.resolve('Invalid API key'),
    });

    render(<EndpointTester modelId="model-1" endpoint={ENDPOINT} />);
    await screen.findByLabelText('age');
    fireEvent.change(screen.getByLabelText('API Key'), {
      target: { value: 'bad' },
    });
    fireEvent.click(screen.getByTestId('run-endpoint-test'));

    expect(await screen.findByTestId('endpoint-tester-error')).toHaveTextContent('401');
  });
});
