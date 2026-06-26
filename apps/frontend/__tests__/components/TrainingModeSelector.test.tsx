import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TrainingModeSelector } from '@/components/TrainingModeSelector';

describe('TrainingModeSelector (issue #101)', () => {
  it('renders both modes with trade-off copy', () => {
    render(<TrainingModeSelector value="quick" onChange={jest.fn()} />);

    expect(screen.getByTestId('mode-option-quick')).toBeInTheDocument();
    expect(screen.getByTestId('mode-option-comprehensive')).toBeInTheDocument();
    expect(screen.getByText('~3 algorithms')).toBeInTheDocument();
    expect(screen.getByText('10+ algorithms')).toBeInTheDocument();
  });

  it('marks the selected mode as checked', () => {
    render(<TrainingModeSelector value="comprehensive" onChange={jest.fn()} />);

    expect(screen.getByTestId('mode-option-comprehensive')).toHaveAttribute(
      'aria-checked',
      'true'
    );
    expect(screen.getByTestId('mode-option-quick')).toHaveAttribute(
      'aria-checked',
      'false'
    );
  });

  it('calls onChange when a mode card is clicked', async () => {
    const onChange = jest.fn();
    render(<TrainingModeSelector value="quick" onChange={onChange} />);

    await userEvent.click(screen.getByTestId('mode-option-comprehensive'));

    expect(onChange).toHaveBeenCalledWith('comprehensive');
  });

  it('shows the recommendation banner and reason when provided', () => {
    render(
      <TrainingModeSelector
        value="quick"
        onChange={jest.fn()}
        recommendedMode="comprehensive"
        reason="small enough to afford a thorough search"
      />
    );

    const banner = screen.getByTestId('mode-recommendation');
    expect(banner).toHaveTextContent('Recommended: Comprehensive');
    expect(banner).toHaveTextContent('small enough to afford a thorough search');
  });

  it('omits the recommendation banner when none is provided', () => {
    render(<TrainingModeSelector value="quick" onChange={jest.fn()} />);
    expect(screen.queryByTestId('mode-recommendation')).not.toBeInTheDocument();
  });

  it('does not call onChange when disabled', async () => {
    const onChange = jest.fn();
    render(
      <TrainingModeSelector value="quick" onChange={onChange} disabled />
    );

    await userEvent.click(screen.getByTestId('mode-option-comprehensive'));
    expect(onChange).not.toHaveBeenCalled();
  });
});
