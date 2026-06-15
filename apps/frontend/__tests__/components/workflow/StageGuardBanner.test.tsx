/**
 * Tests for the global StageGuardBanner (issue #88, AC2).
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { StageGuardBanner } from '@/components/workflow/StageGuardBanner';

const clearGuardMessage = jest.fn();
let guardMessage: string | null;

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({ guardMessage, clearGuardMessage }),
}));

beforeEach(() => {
  clearGuardMessage.mockClear();
  guardMessage = null;
});

describe('StageGuardBanner', () => {
  it('renders nothing when there is no guard message', () => {
    const { container } = render(<StageGuardBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the message and dismisses on click', () => {
    guardMessage = 'Complete "Data Profiling" before you can access "Prediction".';
    render(<StageGuardBanner />);

    expect(screen.getByTestId('stage-guard-banner')).toHaveTextContent(/Data Profiling/);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(clearGuardMessage).toHaveBeenCalledTimes(1);
  });

  it('auto-dismisses after the timeout', () => {
    jest.useFakeTimers();
    try {
      guardMessage = 'Gated.';
      render(<StageGuardBanner />);
      expect(clearGuardMessage).not.toHaveBeenCalled();
      act(() => {
        jest.advanceTimersByTime(8000);
      });
      expect(clearGuardMessage).toHaveBeenCalledTimes(1);
    } finally {
      jest.useRealTimers();
    }
  });
});
