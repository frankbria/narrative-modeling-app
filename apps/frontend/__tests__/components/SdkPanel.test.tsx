import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SdkPanel } from '@/components/SdkPanel';

const mockGetSdkInfo = jest.fn();
const mockGetSdk = jest.fn();
const mockGetSdkPostman = jest.fn();

jest.mock('@/lib/services/model', () => ({
  modelService: {
    getSdkInfo: (...a: unknown[]) => mockGetSdkInfo(...a),
    getSdk: (...a: unknown[]) => mockGetSdk(...a),
    getSdkPostman: (...a: unknown[]) => mockGetSdkPostman(...a),
  },
}));

const INFO = {
  model_id: 'model-1',
  model_name: 'Sales',
  problem_type: 'regression',
  serving_endpoint: 'http://x/api/v1/production/v1/models/model-1',
  predict_url: 'http://x/api/v1/production/v1/models/model-1/predict',
  feature_names: ['month'],
  sample_record: { month: 0 },
  languages: ['python', 'typescript', 'javascript', 'curl'],
  install: { python: 'pip install requests' },
  auth: 'X-API-Key',
  readme: '# Sales — Python SDK\n\npip install requests',
};

describe('SdkPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSdkInfo.mockResolvedValue(INFO);
    mockGetSdk.mockImplementation((_id: string, lang: string) =>
      Promise.resolve(`# ${lang} client source`)
    );
    mockGetSdkPostman.mockResolvedValue({ info: { name: 'Sales API' } });
  });

  it('renders language tabs and loads the default python SDK', async () => {
    render(<SdkPanel modelId="model-1" />);
    expect(await screen.findByRole('tab', { name: 'TypeScript' })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText('# python client source')).toBeInTheDocument()
    );
    expect(mockGetSdk).toHaveBeenCalledWith('model-1', 'python');
  });

  it('switches language and fetches that SDK', async () => {
    render(<SdkPanel modelId="model-1" />);
    const tsTab = await screen.findByRole('tab', { name: 'TypeScript' });
    fireEvent.click(tsTab);
    await waitFor(() =>
      expect(screen.getByText('# typescript client source')).toBeInTheDocument()
    );
    expect(mockGetSdk).toHaveBeenCalledWith('model-1', 'typescript');
  });

  it('downloads the Postman collection on demand', async () => {
    render(<SdkPanel modelId="model-1" />);
    const btn = await screen.findByText('Postman collection');
    fireEvent.click(btn);
    await waitFor(() => expect(mockGetSdkPostman).toHaveBeenCalledWith('model-1'));
  });

  it('shows an error when SDK info fails to load', async () => {
    mockGetSdkInfo.mockRejectedValue(new Error('boom'));
    render(<SdkPanel modelId="model-1" />);
    expect(
      await screen.findByText(/Could not load SDK info/i)
    ).toBeInTheDocument();
  });

  it('renders the SDK README (AC5) from the info payload', async () => {
    render(<SdkPanel modelId="model-1" />);
    expect(
      await screen.findByText('SDK documentation (README)')
    ).toBeInTheDocument();
  });
});
