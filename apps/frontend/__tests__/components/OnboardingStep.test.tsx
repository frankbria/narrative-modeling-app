import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { OnboardingStep } from '@/components/OnboardingStep';

const mockStep = {
  step_id: 'upload_data',
  title: 'Upload Your First Dataset',
  description: 'Learn how to upload and validate your data',
  step_type: 'upload_data',
  status: 'in_progress' as const,
  order: 2,
  is_required: true,
  is_skippable: false,
  estimated_duration: '5 minutes',
  completion_criteria: [
    'Successfully upload a CSV file',
    'Pass data validation checks'
  ],
  instructions: [
    'Choose a CSV file or select a sample dataset',
    'Upload the file using the upload interface',
    'Review the data validation results',
    'Confirm your data looks correct'
  ],
  help_text: 'We\'ll help you upload data and check for any quality issues.',
  code_examples: [
    {
      title: 'Sample CSV Format',
      code: 'customer_id,age,income,churn\nC001,25,50000,0\nC002,35,75000,1'
    }
  ]
};

const mockProps = {
  step: mockStep,
  onComplete: jest.fn(),
  onSkip: jest.fn(),
  isCompleting: false
};

describe('OnboardingStep', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders step information correctly', () => {
    render(<OnboardingStep {...mockProps} />);
    
    expect(screen.getByText('Upload Your First Dataset')).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
    expect(screen.getByText('5 minutes')).toBeInTheDocument();
    expect(screen.getByText('Learn how to upload and validate your data')).toBeInTheDocument();
  });

  it('shows different content based on step type', () => {
    render(<OnboardingStep {...mockProps} />);
    
    // Should show upload-specific content
    expect(screen.getByText(/Ready to upload your first dataset/)).toBeInTheDocument();
    expect(screen.getByText('Upload CSV File')).toBeInTheDocument();
    expect(screen.getByText('Browse Samples')).toBeInTheDocument();
  });

  it('displays tab navigation correctly', () => {
    render(<OnboardingStep {...mockProps} />);
    
    // Check that all tabs are present
    expect(screen.getByText('Content')).toBeInTheDocument();
    expect(screen.getByText('Instructions')).toBeInTheDocument();
    expect(screen.getByText('Criteria')).toBeInTheDocument();
    expect(screen.getByText('Help')).toBeInTheDocument();
  });

  it('calls onComplete when complete button is clicked', async () => {
    render(<OnboardingStep {...mockProps} />);
    
    const completeButton = screen.getByText('Mark as Complete');
    fireEvent.click(completeButton);
    
    await waitFor(() => {
      expect(mockProps.onComplete).toHaveBeenCalledWith('upload_data', {});
    });
  });


  it('Browse Samples reveals the sample selector, then loading a sample navigates to it (#281)', async () => {
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

    global.fetch = jest.fn((url: string, init?: RequestInit) => {
      if (typeof url === 'string' && url.includes('/load')) {
        // Backend returns the id of the newly created UserData record, which is
        // what the caller must navigate to (NOT the sample slug).
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, dataset_id: 'real-userdata-123' }),
        });
      }
      // sample-datasets listing
      return Promise.resolve({ ok: true, json: async () => [sampleDataset] });
    }) as jest.Mock;

    render(<OnboardingStep {...mockProps} />);

    // Selector is hidden until Browse Samples is clicked (state change).
    expect(screen.queryByText('Choose a Sample Dataset')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Browse Samples'));

    // Selector appears and loads the available datasets.
    expect(await screen.findByText('Choose a Sample Dataset')).toBeInTheDocument();
    expect(await screen.findByText('Customer Churn')).toBeInTheDocument();

    // Load the sample → advance to the created dataset.
    fireEvent.click(screen.getByText('Use This'));

    await waitFor(() => {
      expect((global as any).__NEXT_ROUTER_MOCKS__.push).toHaveBeenCalledWith(
        '/explore/real-userdata-123'
      );
    });
  });

  it('surfaces an error (no silent dead-end) when a sample fails to load (#281)', async () => {
    const sampleDataset = {
      dataset_id: 'customer_churn',
      name: 'Customer Churn',
      description: 'Predict churn',
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

    global.fetch = jest.fn((url: string) => {
      if (typeof url === 'string' && url.includes('/load')) {
        // Backend rejected (e.g. sample file missing) — must not silently pass.
        return Promise.resolve({ ok: false, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => [sampleDataset] });
    }) as jest.Mock;

    render(<OnboardingStep {...mockProps} />);
    fireEvent.click(screen.getByText('Browse Samples'));
    fireEvent.click(await screen.findByText('Use This'));

    expect(await screen.findByText(/couldn't load/i)).toBeInTheDocument();
    expect((global as any).__NEXT_ROUTER_MOCKS__.push).not.toHaveBeenCalled();
  });

  it('does not show skip button for non-skippable step', () => {
    render(<OnboardingStep {...mockProps} />);
    
    expect(screen.queryByText('Skip Step')).not.toBeInTheDocument();
  });

  it('shows completion alert for completed step', () => {
    const completedStep = {
      ...mockStep,
      status: 'completed' as const
    };
    
    render(<OnboardingStep {...mockProps} step={completedStep} />);
    
    expect(screen.getByText('✅ Step completed successfully!')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('shows loading state when completing', () => {
    render(<OnboardingStep {...mockProps} isCompleting={true} />);
    
    expect(screen.getByText('Completing...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /completing/i })).toBeDisabled();
  });

  it('renders welcome step content without the inert video button (#281)', () => {
    const welcomeStep = {
      ...mockStep,
      step_type: 'welcome',
      title: 'Welcome to Narrative Modeling',
      video_url: '/videos/welcome'
    };

    render(<OnboardingStep {...mockProps} step={welcomeStep} />);

    expect(screen.getByText('Welcome to the Platform! 🚀')).toBeInTheDocument();
    // The "Watch Introduction" button was a dead-end (no player) and is removed.
    expect(screen.queryByText('Watch Introduction')).not.toBeInTheDocument();
  });

  it('renders explore data step content correctly', () => {
    const exploreStep = {
      ...mockStep,
      step_type: 'explore_data',
      title: 'Explore Your Data'
    };
    
    render(<OnboardingStep {...mockProps} step={exploreStep} />);
    
    expect(screen.getByText('Understand Your Data 📊')).toBeInTheDocument();
    expect(screen.getByText('Statistics')).toBeInTheDocument();
    expect(screen.getByText('Quality Check')).toBeInTheDocument();
    expect(screen.getByText('Visualizations')).toBeInTheDocument();
  });

  it('renders train model step content correctly', () => {
    const trainStep = {
      ...mockStep,
      step_type: 'train_model',
      title: 'Train Your Model'
    };
    
    render(<OnboardingStep {...mockProps} step={trainStep} />);
    
    expect(screen.getByText('Train Your Model 🤖')).toBeInTheDocument();
    expect(screen.getByText(/AutoML technology will/)).toBeInTheDocument();
    expect(screen.getByText('Start Training')).toBeInTheDocument();
  });

  it('renders make predictions step content correctly', () => {
    const predictStep = {
      ...mockStep,
      step_type: 'make_predictions',
      title: 'Make Predictions'
    };
    
    render(<OnboardingStep {...mockProps} step={predictStep} />);
    
    expect(screen.getByText('Make Predictions 🎯')).toBeInTheDocument();
    expect(screen.getByText(/put it to work/)).toBeInTheDocument();
    // Use getAllByText since there are multiple instances of this text
    expect(screen.getAllByText('Make Predictions')).toHaveLength(2); // Title and button
  });

  it('renders export model step content correctly', () => {
    const exportStep = {
      ...mockStep,
      step_type: 'export_model',
      title: 'Export & Deploy'
    };
    
    render(<OnboardingStep {...mockProps} step={exportStep} />);
    
    expect(screen.getByText('Export & Deploy 📦')).toBeInTheDocument();
    expect(screen.getByText('🐍 Python Code')).toBeInTheDocument();
    expect(screen.getByText('🐳 Docker Container')).toBeInTheDocument();
  });

  it('handles step type icon display correctly', () => {
    const steps = [
      { ...mockStep, step_type: 'welcome' },
      { ...mockStep, step_type: 'upload_data' },
      { ...mockStep, step_type: 'explore_data' },
      { ...mockStep, step_type: 'train_model' },
      { ...mockStep, step_type: 'make_predictions' },
      { ...mockStep, step_type: 'export_model' },
      { ...mockStep, step_type: 'completion' }
    ];

    steps.forEach(step => {
      const { unmount } = render(<OnboardingStep {...mockProps} step={step} />);
      // Icons are rendered as text emojis, check they exist
      expect(document.body).toContainHTML('</span>'); // Some icon should be present
      unmount();
    });
  });

  it('handles step type color coding correctly', () => {
    const { rerender } = render(<OnboardingStep {...mockProps} />);
    
    // Check that step badges have appropriate styling
    expect(screen.getByText('Step 2')).toHaveClass('bg-green-100', 'text-green-800');
    
    const welcomeStep = { ...mockStep, step_type: 'welcome', order: 1 };
    rerender(<OnboardingStep {...mockProps} step={welcomeStep} />);
    expect(screen.getByText('Step 1')).toHaveClass('bg-blue-100', 'text-blue-800');
  });
});