import React from 'react';
import { render, screen } from '@testing-library/react';
import { ImportanceIndicator } from '@/components/ImportanceIndicator';

describe('ImportanceIndicator', () => {
  it('renders with percentage label', () => {
    render(<ImportanceIndicator score={0.75} />);

    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('renders without label when showLabel is false', () => {
    render(<ImportanceIndicator score={0.75} showLabel={false} />);

    expect(screen.queryByText('75%')).not.toBeInTheDocument();
  });

  it('renders progress bar with correct role', () => {
    render(<ImportanceIndicator score={0.5} />);

    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveAttribute('aria-valuenow', '50');
  });

  it('displays high importance (green) for scores >= 0.7', () => {
    const { container } = render(<ImportanceIndicator score={0.85} />);

    const progressFill = container.querySelector('.bg-green-500');
    expect(progressFill).toBeInTheDocument();
  });

  it('displays medium importance (yellow) for scores between 0.4 and 0.7', () => {
    const { container } = render(<ImportanceIndicator score={0.55} />);

    const progressFill = container.querySelector('.bg-yellow-500');
    expect(progressFill).toBeInTheDocument();
  });

  it('displays low importance (orange) for scores < 0.4', () => {
    const { container } = render(<ImportanceIndicator score={0.25} />);

    const progressFill = container.querySelector('.bg-orange-500');
    expect(progressFill).toBeInTheDocument();
  });

  it('respects size prop for small size', () => {
    const { container } = render(<ImportanceIndicator score={0.5} size="sm" />);

    const progressBar = container.querySelector('.h-1\\.5');
    expect(progressBar).toBeInTheDocument();
  });

  it('respects size prop for large size', () => {
    const { container } = render(<ImportanceIndicator score={0.5} size="lg" />);

    const progressBar = container.querySelector('.h-2\\.5');
    expect(progressBar).toBeInTheDocument();
  });

  it('rounds percentage correctly', () => {
    render(<ImportanceIndicator score={0.756} />);

    expect(screen.getByText('76%')).toBeInTheDocument();
  });

  it('handles edge case of 0 score', () => {
    render(<ImportanceIndicator score={0} />);

    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  it('handles edge case of 1.0 score', () => {
    render(<ImportanceIndicator score={1.0} />);

    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <ImportanceIndicator score={0.5} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });
});
