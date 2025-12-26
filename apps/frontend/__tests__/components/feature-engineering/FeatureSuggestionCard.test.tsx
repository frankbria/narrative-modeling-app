import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { FeatureSuggestionCard } from '@/components/FeatureSuggestionCard';
import { FeatureSuggestion, FeatureType, ComputationCost } from '@/lib/hooks/useFeatureSuggestions';

const mockSuggestion: FeatureSuggestion = {
  id: 'feat_test_001',
  name: 'age_squared',
  description: 'Square of the age column for polynomial regression',
  feature_type: 'polynomial' as FeatureType,
  formula: 'age ** 2',
  expected_importance: 0.75,
  explanation: 'Polynomial features can capture non-linear relationships. Age often has diminishing or accelerating effects.',
  computation_cost: 'low' as ComputationCost,
  input_columns: ['age'],
  parameters: { power: 2 },
  source: 'rule_based',
};

const mockAiSuggestion: FeatureSuggestion = {
  id: 'feat_ai_001',
  name: 'customer_lifetime_value',
  description: 'Estimated customer lifetime value based on purchase history',
  feature_type: 'domain_specific' as FeatureType,
  formula: 'avg_order_value * order_frequency * customer_tenure',
  expected_importance: 0.85,
  explanation: 'CLV is a key metric for understanding customer profitability.',
  computation_cost: 'medium' as ComputationCost,
  input_columns: ['avg_order_value', 'order_frequency', 'customer_tenure'],
  parameters: {},
  source: 'ai',
};

describe('FeatureSuggestionCard', () => {
  it('renders suggestion name and description', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    expect(screen.getByText('age_squared')).toBeInTheDocument();
    expect(screen.getByText(/Square of the age column/)).toBeInTheDocument();
  });

  it('displays feature type badge', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    expect(screen.getByText('Polynomial')).toBeInTheDocument();
  });

  it('displays computation cost badge', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    expect(screen.getByText('Fast')).toBeInTheDocument();
  });

  it('displays AI badge for AI-generated suggestions', () => {
    render(<FeatureSuggestionCard suggestion={mockAiSuggestion} />);

    expect(screen.getByText('AI')).toBeInTheDocument();
  });

  it('does not display AI badge for rule-based suggestions', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    expect(screen.queryByText('AI')).not.toBeInTheDocument();
  });

  it('displays formula in code block', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    expect(screen.getByText('age ** 2')).toBeInTheDocument();
  });

  it('displays input columns', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    expect(screen.getByText('age')).toBeInTheDocument();
  });

  it('shows multiple input columns', () => {
    render(<FeatureSuggestionCard suggestion={mockAiSuggestion} />);

    expect(screen.getByText('avg_order_value')).toBeInTheDocument();
    expect(screen.getByText('order_frequency')).toBeInTheDocument();
    expect(screen.getByText('customer_tenure')).toBeInTheDocument();
  });

  it('expands to show explanation when toggle clicked', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    // Initially explanation should not be visible
    expect(screen.queryByText(/Polynomial features can capture/)).not.toBeInTheDocument();

    // Click to expand
    const toggleButton = screen.getByText('Show explanation');
    fireEvent.click(toggleButton);

    // Now explanation should be visible
    expect(screen.getByText(/Polynomial features can capture/)).toBeInTheDocument();
  });

  it('calls onAccept when Accept button clicked', () => {
    const onAccept = jest.fn();
    render(<FeatureSuggestionCard suggestion={mockSuggestion} onAccept={onAccept} />);

    const acceptButton = screen.getByRole('button', { name: /Accept/i });
    fireEvent.click(acceptButton);

    expect(onAccept).toHaveBeenCalledWith(mockSuggestion);
  });

  it('calls onReject when reject button clicked', () => {
    const onReject = jest.fn();
    render(<FeatureSuggestionCard suggestion={mockSuggestion} onReject={onReject} />);

    // Find the reject button (the one that is NOT the Accept button)
    const buttons = screen.getAllByRole('button');
    // Reject button is the second button in the actions area (after Accept)
    const rejectButton = buttons.find((btn) =>
      btn.textContent?.trim() === '' && btn.querySelector('svg')
    );

    expect(rejectButton).toBeDefined();
    if (rejectButton) {
      fireEvent.click(rejectButton);
    }

    expect(onReject).toHaveBeenCalled();
  });

  it('shows selected state when isSelected is true', () => {
    const { container } = render(
      <FeatureSuggestionCard suggestion={mockSuggestion} isSelected={true} />
    );

    // Should have ring class for selected state
    const card = container.firstChild;
    expect(card).toHaveClass('ring-2');
  });

  it('disables Accept button when selected', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} isSelected={true} />);

    const acceptButton = screen.getByRole('button', { name: /Added/i });
    expect(acceptButton).toBeDisabled();
  });

  it('renders importance indicator', () => {
    render(<FeatureSuggestionCard suggestion={mockSuggestion} />);

    // Should show 75% importance
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('handles suggestions without formula gracefully', () => {
    const noFormulaSuggestion = { ...mockSuggestion, formula: null };
    render(<FeatureSuggestionCard suggestion={noFormulaSuggestion} />);

    // Should render without error
    expect(screen.getByText('age_squared')).toBeInTheDocument();
  });
});
