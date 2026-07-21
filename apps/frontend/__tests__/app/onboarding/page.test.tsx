import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OnboardingPage from '@/app/onboarding/page';

// Radix tab triggers need the full pointer sequence in JSDOM.
const activateTab = (name: RegExp) => {
  const tab = screen.getByRole('tab', { name });
  fireEvent.mouseDown(tab);
  fireEvent.mouseUp(tab);
  fireEvent.click(tab);
};

const sampleDataset = {
  dataset_id: 'customer_churn',
  name: 'Customer Churn',
  description: 'Predict which customers will churn',
  size_mb: 1,
  rows: 1000,
  columns: 8,
  problem_type: 'binary_classification',
  difficulty_level: 'beginner',
  tags: ['classification'],
  preview_data: [{ customer_id: 'C001', churn: 0 }],
  target_column: 'churn',
  feature_columns: ['customer_id'],
  learning_objectives: ['Learn classification'],
  download_url: '/download/customer_churn',
};

const mockFetch = (url: string, init?: RequestInit) => {
  const u = String(url);
  if (u.includes('/onboarding/status')) {
    return Promise.resolve({
      ok: true,
      json: async () => ({ is_onboarding_complete: false, current_step_id: null }),
    });
  }
  if (u.includes('/sample-datasets') && u.includes('/load')) {
    return Promise.resolve({
      ok: true,
      json: async () => ({ success: true, dataset_id: 'real-userdata-123' }),
    });
  }
  if (u.includes('/sample-datasets')) {
    return Promise.resolve({ ok: true, json: async () => [sampleDataset] });
  }
  if (u.includes('/onboarding/steps')) {
    return Promise.resolve({ ok: true, json: async () => [] });
  }
  if (u.includes('/onboarding/achievements')) {
    return Promise.resolve({ ok: true, json: async () => ({ achievements: [] }) });
  }
  return Promise.resolve({ ok: true, json: async () => ({}) });
};

describe('OnboardingPage (#281 dead controls)', () => {
  beforeEach(() => {
    global.fetch = jest.fn(mockFetch) as jest.Mock;
  });

  it('loading a sample dataset from the Sample Data tab navigates to it', async () => {
    render(<OnboardingPage />);

    // Welcome card renders once loading resolves.
    expect(
      await screen.findByText('Welcome to Narrative Modeling!')
    ).toBeInTheDocument();

    activateTab(/sample data/i);

    fireEvent.click(await screen.findByText('Use This'));

    await waitFor(() => {
      expect((global as any).__NEXT_ROUTER_MOCKS__.push).toHaveBeenCalledWith(
        '/explore/real-userdata-123'
      );
    });
  });

  it('Help tab documentation buttons link to the real /quickstart page', async () => {
    render(<OnboardingPage />);
    await screen.findByText('Welcome to Narrative Modeling!');

    activateTab(/help & resources/i);

    const docLink = await screen.findByRole('link', {
      name: /understanding data quality/i,
    });
    expect(docLink).toHaveAttribute('href', '/quickstart');
  });

  it('removes the inert video-tutorial buttons', async () => {
    render(<OnboardingPage />);
    await screen.findByText('Welcome to Narrative Modeling!');

    activateTab(/help & resources/i);
    await screen.findByRole('link', { name: /understanding data quality/i });

    // The placeholder "Video Tutorials" buttons pointed at nothing — gone now.
    expect(screen.queryByText('Platform Overview (3 min)')).not.toBeInTheDocument();
    expect(screen.queryByText('Video Tutorials')).not.toBeInTheDocument();
  });
});
