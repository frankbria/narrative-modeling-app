import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { NotificationPreferences } from '@/components/settings/NotificationPreferences';
import { notificationPreferencesApi } from '@/lib/services/notificationPreferences';

jest.mock('@/lib/services/notificationPreferences', () => ({
  notificationPreferencesApi: { get: jest.fn(), setJobEmails: jest.fn() },
}));

const api = notificationPreferencesApi as jest.Mocked<typeof notificationPreferencesApi>;

const jobEmailsSwitch = () => screen.getByRole('switch', { name: /email me when a job finishes or fails/i });

async function renderedWith(jobEmails: boolean) {
  api.get.mockResolvedValue({ job_emails: jobEmails });
  render(<NotificationPreferences />);
  await waitFor(() => expect(jobEmailsSwitch()).toBeEnabled());
}

describe('NotificationPreferences (#494)', () => {
  beforeEach(() => jest.resetAllMocks());

  it('cannot be changed until the stored choice has loaded', () => {
    api.get.mockReturnValue(new Promise(() => {}));

    render(<NotificationPreferences />);

    expect(jobEmailsSwitch()).toBeDisabled();
  });

  it.each([
    [true, 'true'],
    [false, 'false'],
  ])('shows the stored choice (%s)', async (stored, ariaChecked) => {
    await renderedWith(stored);

    expect(jobEmailsSwitch()).toHaveAttribute('aria-checked', ariaChecked);
  });

  it('saves the new choice when the switch is turned off', async () => {
    api.setJobEmails.mockResolvedValue({ job_emails: false });
    await renderedWith(true);

    fireEvent.click(jobEmailsSwitch());

    expect(api.setJobEmails).toHaveBeenCalledWith(false);
    await waitFor(() => expect(jobEmailsSwitch()).toHaveAttribute('aria-checked', 'false'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('puts the switch back and says so when the save fails', async () => {
    api.setJobEmails.mockRejectedValue(new Error('Database unavailable'));
    await renderedWith(true);

    fireEvent.click(jobEmailsSwitch());

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/could not save/i));
    expect(jobEmailsSwitch()).toHaveAttribute('aria-checked', 'true');
  });

  it('says the choice could not be loaded, and offers no switch to guess with', async () => {
    api.get.mockRejectedValue(new Error('offline'));

    render(<NotificationPreferences />);

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/could not load/i));
    expect(jobEmailsSwitch()).toBeDisabled();
  });
});
