import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FeedbackWidget } from '@/components/FeedbackWidget';

describe('FeedbackWidget', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('renders a floating button when collapsed', () => {
    render(<FeedbackWidget />);
    expect(screen.getByTestId('feedback-widget-button')).toBeInTheDocument();
    expect(screen.queryByTestId('feedback-widget-panel')).not.toBeInTheDocument();
  });

  it('opens the form when the button is clicked', async () => {
    const user = userEvent.setup();
    render(<FeedbackWidget />);

    await user.click(screen.getByTestId('feedback-widget-button'));
    expect(screen.getByTestId('feedback-widget-panel')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-message')).toBeInTheDocument();
  });

  it('validates that a rating is required', async () => {
    const user = userEvent.setup();
    render(<FeedbackWidget />);

    await user.click(screen.getByTestId('feedback-widget-button'));
    await user.type(screen.getByTestId('feedback-message'), 'Nice app');
    await user.click(screen.getByTestId('feedback-submit'));

    expect(screen.getByTestId('feedback-error')).toHaveTextContent(/star rating/i);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('validates that a message is required', async () => {
    const user = userEvent.setup();
    render(<FeedbackWidget />);

    await user.click(screen.getByTestId('feedback-widget-button'));
    await user.click(screen.getByTestId('feedback-star-4'));
    await user.click(screen.getByTestId('feedback-submit'));

    expect(screen.getByTestId('feedback-error')).toHaveTextContent(/message/i);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('submits feedback and shows a success state', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({ feedback_id: 'fb_123' }),
    });

    render(<FeedbackWidget />);
    await user.click(screen.getByTestId('feedback-widget-button'));
    await user.click(screen.getByTestId('feedback-star-5'));
    await user.selectOptions(screen.getByTestId('feedback-category'), 'bug');
    await user.type(screen.getByTestId('feedback-message'), 'Found an issue');
    await user.click(screen.getByTestId('feedback-submit'));

    await waitFor(() =>
      expect(screen.getByTestId('feedback-success')).toBeInTheDocument()
    );

    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain('/feedback');
    expect(options.method).toBe('POST');
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({
      rating: 5,
      category: 'bug',
      message: 'Found an issue',
    });
    expect(body).toHaveProperty('page_context');
  });

  it('shows an error state when submission fails', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 500 });

    render(<FeedbackWidget />);
    await user.click(screen.getByTestId('feedback-widget-button'));
    await user.click(screen.getByTestId('feedback-star-3'));
    await user.type(screen.getByTestId('feedback-message'), 'Broken');
    await user.click(screen.getByTestId('feedback-submit'));

    await waitFor(() =>
      expect(screen.getByTestId('feedback-error')).toBeInTheDocument()
    );
    expect(screen.queryByTestId('feedback-success')).not.toBeInTheDocument();
  });
});
