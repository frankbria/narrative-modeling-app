/**
 * The admin page shows only measured values (#478).
 *
 * The page used to hardcode a security-status card and a sprint retrospective,
 * shown to customers as fact. These assert that fabricated narrative is gone and
 * that the one live widget still renders.
 */
import { render, screen } from '@testing-library/react';

import AdminPage from '@/app/admin/page';

jest.mock('@/components/HealthMonitor', () => ({
  HealthMonitor: () => <div data-testid="health-monitor" />,
}));

describe('AdminPage (#478)', () => {
  it('renders the live health widget, not fabricated status', () => {
    render(<AdminPage />);
    expect(screen.getByTestId('health-monitor')).toBeInTheDocument();
  });

  it.each([
    'Sprint 1',
    'fully operational',
    'PII Detection',
    'Upload Security',
    'SHA-256',
    'Achievement Summary',
    '41/41 tests passing',
    '100% Complete',
  ])('does not render the fabricated literal %p', (literal) => {
    render(<AdminPage />);
    expect(screen.queryByText(new RegExp(literal, 'i'))).not.toBeInTheDocument();
  });
});
