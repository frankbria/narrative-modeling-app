import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { CancelTrainingButton } from '@/components/training/CancelTrainingButton';

const mockCancelTraining = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    cancelTraining: (...args: unknown[]) => mockCancelTraining(...args),
  },
}));

describe('CancelTrainingButton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('opens a confirmation dialog explaining the cancellation behavior', async () => {
    render(<CancelTrainingButton modelId="m1" />);

    await userEvent.click(screen.getByRole('button', { name: /Cancel Training/i }));

    expect(await screen.findByText(/Cancel training\?/i)).toBeInTheDocument();
    expect(
      screen.getByText(/The current algorithm will finish, then training stops\./i)
    ).toBeInTheDocument();
  });

  it('confirming calls cancelTraining, fires onCancelled and closes the dialog', async () => {
    const response = {
      model_id: 'm1',
      status: 'running',
      cancellation_requested: true,
      message: 'Cancellation requested',
    };
    mockCancelTraining.mockResolvedValue(response);
    const onCancelled = jest.fn();

    render(<CancelTrainingButton modelId="m1" onCancelled={onCancelled} />);

    await userEvent.click(screen.getByRole('button', { name: /Cancel Training/i }));
    await userEvent.click(
      await screen.findByRole('button', { name: /Yes, cancel training/i })
    );

    await waitFor(() => expect(onCancelled).toHaveBeenCalledWith(response));
    expect(mockCancelTraining).toHaveBeenCalledWith('m1');
    await waitFor(() =>
      expect(screen.queryByText(/Cancel training\?/i)).not.toBeInTheDocument()
    );
  });

  it('shows the backend error inline and keeps the dialog open on failure', async () => {
    mockCancelTraining.mockRejectedValue(new Error('Training job already completed'));

    render(<CancelTrainingButton modelId="m1" />);

    await userEvent.click(screen.getByRole('button', { name: /Cancel Training/i }));
    await userEvent.click(
      await screen.findByRole('button', { name: /Yes, cancel training/i })
    );

    expect(
      await screen.findByText('Training job already completed')
    ).toBeInTheDocument();
    expect(screen.getByText(/Cancel training\?/i)).toBeInTheDocument();
  });

  it('respects the disabled prop on the trigger button', () => {
    render(<CancelTrainingButton modelId="m1" disabled />);

    expect(screen.getByRole('button', { name: /Cancel Training/i })).toBeDisabled();
  });
});
