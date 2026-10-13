/**
 * The onboarding page as a shell over components/onboarding (#809): which view it
 * shows, what the sidebar selects, and what its two actions do. What the layout
 * looks like at a given width is measured in a browser (e2e onboarding.spec), since
 * jsdom lays nothing out.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import OnboardingPage from '@/app/onboarding/page';
import { onboardingApi } from '@/lib/services/onboarding';

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => ({ completeStage: jest.fn() }),
}));
jest.mock('@/lib/services/onboarding', () => ({
  onboardingApi: {
    getStatus: jest.fn(),
    getSteps: jest.fn(),
    getAchievements: jest.fn(),
    completeStep: jest.fn(),
    skipStep: jest.fn(),
    getSampleDatasets: jest.fn(async () => []),
    loadSampleDataset: jest.fn(),
  },
}));

const api = onboardingApi as jest.Mocked<typeof onboardingApi>;

const step = (order: number, step_id: string, title: string, status = 'not_started') => ({
  step_id,
  title,
  description: `${title} description`,
  step_type: 'tutorial',
  status,
  order,
  is_required: true,
  is_skippable: true,
  estimated_duration: '5 minutes',
  completion_criteria: ['Do it'],
  instructions: ['Step one'],
});

const STEPS = [
  step(1, 'welcome', 'Welcome to Narrative Modeling', 'completed'),
  step(2, 'upload_data', 'Upload Your First Dataset', 'in_progress'),
  step(3, 'explore_data', 'Explore Your Data'),
];

const status = (overrides: Record<string, unknown> = {}) => ({
  user_id: 'u1',
  is_onboarding_complete: false,
  current_step_id: null,
  progress_percentage: 33,
  total_steps: 3,
  completed_steps: 1,
  skipped_steps: 0,
  time_spent_minutes: 4,
  started_at: '2026-10-01T00:00:00Z',
  completed_at: null,
  last_activity_at: '2026-10-01T00:00:00Z',
  ...overrides,
});

const BADGE = { id: 'b1', title: 'Data Explorer', description: 'd', type: 'badge', points: 10, earned_at: '2026-10-01T00:00:00Z' };

function serve(overrides: { status?: Record<string, unknown>; achievements?: unknown[] } = {}) {
  api.getStatus.mockResolvedValue(status(overrides.status));
  api.getSteps.mockResolvedValue(STEPS);
  api.getAchievements.mockResolvedValue({ achievements: overrides.achievements || [] });
}

const sidebar = () => within(screen.getByTestId('onboarding-sidebar'));
const stepButton = (title: string) => sidebar().getByRole('button', { name: new RegExp(title) });

describe('OnboardingPage flow (#809)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('lists every step with its full title, and opens the one that is clicked', async () => {
    serve();
    render(<OnboardingPage />);

    expect(await screen.findByText('Welcome to Narrative Modeling!')).toBeInTheDocument();
    expect(sidebar().getAllByTestId('onboarding-step-title').map((t) => t.textContent)).toEqual(STEPS.map((s) => s.title));
    expect(stepButton('Explore Your Data')).not.toHaveAttribute('aria-current');

    fireEvent.click(stepButton('Explore Your Data'));

    expect(stepButton('Explore Your Data')).toHaveAttribute('aria-current', 'step');
    expect(screen.getAllByText('Explore Your Data description').length).toBeGreaterThan(0);
    expect(screen.queryByText('Welcome to Narrative Modeling!')).not.toBeInTheDocument();
  });

  it('opens the step the backend says is current, and Start Tutorial opens the first', async () => {
    serve({ status: { current_step_id: 'upload_data' } });
    const { unmount } = render(<OnboardingPage />);
    expect((await screen.findAllByText('Upload Your First Dataset description')).length).toBeGreaterThan(0);
    unmount();

    serve();
    render(<OnboardingPage />);
    fireEvent.click(await screen.findByRole('button', { name: /start tutorial/i }));
    expect(screen.getAllByText('Welcome to Narrative Modeling description').length).toBeGreaterThan(0);
  });

  it('completing a step that earns something celebrates and reloads the progress', async () => {
    serve({ status: { current_step_id: 'upload_data' } });
    api.completeStep.mockResolvedValue({ success: true, achievements: [BADGE] });
    render(<OnboardingPage />);

    fireEvent.click(await screen.findByRole('button', { name: /mark as complete/i }));

    expect(await screen.findByText(/you.ve earned new achievements/i)).toBeInTheDocument();
    expect(api.completeStep).toHaveBeenCalledWith('upload_data', expect.any(Object));
    await waitFor(() => expect(api.getStatus).toHaveBeenCalledTimes(2));
  });

  it('a step the backend does not accept, or cannot save, changes nothing and says so', async () => {
    serve({ status: { current_step_id: 'upload_data' } });
    api.completeStep.mockResolvedValueOnce({ success: false });
    render(<OnboardingPage />);

    fireEvent.click(await screen.findByRole('button', { name: /mark as complete/i }));
    await waitFor(() => expect(api.completeStep).toHaveBeenCalledTimes(1));
    expect(api.getStatus).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/earned new achievements/i)).not.toBeInTheDocument();

    api.completeStep.mockRejectedValueOnce(new Error('502'));
    fireEvent.click(screen.getByRole('button', { name: /mark as complete/i }));
    expect(await screen.findByText("Couldn't save that step. Please try again.")).toBeInTheDocument();
  });

  it('skipping a step reloads, and a failed skip says so', async () => {
    serve({ status: { current_step_id: 'upload_data' } });
    api.skipStep.mockResolvedValueOnce({});
    render(<OnboardingPage />);

    fireEvent.click(await screen.findByRole('button', { name: /skip step/i }));
    await waitFor(() => expect(api.getStatus).toHaveBeenCalledTimes(2));
    expect(api.skipStep).toHaveBeenCalledWith('upload_data');

    api.skipStep.mockRejectedValueOnce(new Error('502'));
    fireEvent.click(await screen.findByRole('button', { name: /skip step/i }));
    expect(await screen.findByText("Couldn't skip that step. Please try again.")).toBeInTheDocument();
  });

  it('shows the completion screen, with what was earned, once the tutorial is done', async () => {
    serve({ status: { is_onboarding_complete: true, completed_steps: 3, time_spent_minutes: 21 }, achievements: [BADGE] });
    render(<OnboardingPage />);

    expect(await screen.findByText('Congratulations! 🎉')).toBeInTheDocument();
    expect(screen.getByText('Steps Completed').previousElementSibling).toHaveTextContent('3');
    expect(screen.getByText('Minutes Spent').previousElementSibling).toHaveTextContent('21');
    expect(screen.getByText('Your Achievements')).toBeInTheDocument();
    expect(screen.queryByTestId('onboarding-sidebar')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /start building models/i }));
    fireEvent.click(screen.getByRole('button', { name: /view documentation/i }));
    const { push } = (global as unknown as { __NEXT_ROUTER_MOCKS__: { push: jest.Mock } }).__NEXT_ROUTER_MOCKS__;
    expect(push.mock.calls.map((c) => c[0])).toEqual(['/explore', '/quickstart']);
  });

  it('a completion screen with nothing earned has no achievements section', async () => {
    serve({ status: { is_onboarding_complete: true } });
    render(<OnboardingPage />);

    expect(await screen.findByText('Congratulations! 🎉')).toBeInTheDocument();
    expect(screen.queryByText('Your Achievements')).not.toBeInTheDocument();
  });

  it('Retry loads again after a failed load', async () => {
    serve();
    api.getStatus.mockRejectedValueOnce(new Error('502'));
    render(<OnboardingPage />);

    fireEvent.click(await screen.findByRole('button', { name: /retry/i }));

    expect(await screen.findByText('Welcome to Narrative Modeling!')).toBeInTheDocument();
    expect(api.getStatus).toHaveBeenCalledTimes(2);
  });
});
