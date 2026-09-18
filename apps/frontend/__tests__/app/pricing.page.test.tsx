/**
 * Public pricing page (issue #475).
 *
 * The assertions are written against the shared plan source, not against
 * literals: every number the page shows must be the one in
 * `lib/billing/plans.json`, which the backend holds equal to `plans.py`
 * (`test_pricing_source_matches_plans.py`). A page that hard-coded a limit
 * would pass a literal test and drift silently — this one fails instead.
 */

import { render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import PricingPage, { metadata } from '@/app/pricing/page';
import { COMPANY } from '@/lib/legal/company';
import {
  METRIC_LABELS,
  PLANS,
  UNLIMITED,
  limitLabel,
  planFor,
  priceLabel,
  type Metric,
} from '@/lib/billing/plans';

const METRICS = Object.keys(METRIC_LABELS) as Metric[];

describe('Pricing page', () => {
  it('has a heading and page metadata', () => {
    render(<PricingPage />);
    expect(screen.getByRole('heading', { level: 1, name: /pricing/i })).toBeInTheDocument();
    expect(metadata.title).toMatch(/pricing/i);
  });

  it('lists every tier with its price and every metered limit from the shared source (AC1, AC2)', () => {
    render(<PricingPage />);
    expect(PLANS.length).toBe(3);
    for (const plan of PLANS) {
      const card = screen.getByRole('region', { name: new RegExp(`^${plan.name}$`, 'i') });
      expect(within(card).getByText(priceLabel(plan))).toBeInTheDocument();
      for (const metric of METRICS) {
        const row = within(card).getByText(METRIC_LABELS[metric]).closest('li')!;
        expect(row).toHaveTextContent(limitLabel(plan.limits[metric]));
      }
    }
  });

  it('renders an unlimited limit as the word, never as -1', () => {
    render(<PricingPage />);
    const enterprise = planFor('enterprise');
    expect(Object.values(enterprise.limits)).toContain(UNLIMITED); // the case exists
    expect(screen.queryByText(/-1/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/^unlimited$/i).length).toBeGreaterThan(0);
  });

  it('sells Enterprise by contact, never a price (ADR-003 AC3)', () => {
    render(<PricingPage />);
    const card = screen.getByRole('region', { name: /^enterprise$/i });
    expect(within(card).queryByText(/\$/)).not.toBeInTheDocument();
    expect(within(card).getByRole('link', { name: /contact us/i })).toHaveAttribute(
      'href',
      expect.stringContaining(`mailto:${COMPANY.supportEmail}`),
    );
  });

  it('sends Free and Pro visitors to sign in, Pro landing on the billing page', () => {
    render(<PricingPage />);
    const free = screen.getByRole('region', { name: /^free$/i });
    expect(within(free).getByRole('link', { name: /get started/i })).toHaveAttribute('href', '/auth/signin');
    const pro = screen.getByRole('region', { name: /^pro$/i });
    expect(within(pro).getByRole('link', { name: /upgrade to pro/i })).toHaveAttribute(
      'href',
      expect.stringMatching(/^\/auth\/signin\?callbackUrl=/),
    );
  });

  it('states plainly what happens at a limit: refused with a 402, not queued, no overage (AC4)', () => {
    render(<PricingPage />);
    const section = screen
      .getByRole('heading', { name: /what happens when you reach a limit/i })
      .closest('section')!;
    expect(section).toHaveAttribute('id', 'limits');
    const text = section.textContent ?? '';
    expect(text).toMatch(/402/);
    expect(text).toMatch(/refused/i);
    expect(text).toMatch(/not queued|nothing is queued/i);
    expect(text).toMatch(/no overage|never charged more|not billed as overage/i);
    expect(text).toMatch(/calendar month/i);
  });

  it('links the terms and the refund policy, with the published refund window', () => {
    render(<PricingPage />);
    expect(screen.getByRole('link', { name: /refund policy/i })).toHaveAttribute('href', '/legal/terms#refunds');
    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute('href', '/legal/terms');
    expect(screen.getByText(new RegExp(`${COMPANY.refundWindowDays}-day`, 'i'))).toBeInTheDocument();
  });
});
