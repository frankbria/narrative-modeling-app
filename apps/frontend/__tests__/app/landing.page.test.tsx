/**
 * Public landing page at `/` (issue #766).
 *
 * Written against the sources the copy must come from, not against prose: the
 * name and value line from `COMPANY` (pinned to docs/product/positioning.md),
 * the prices from `PLANS`, the stages from `WORKFLOW_STAGES`. A page that
 * hard-coded any of them passes a literal test and drifts silently; this one
 * fails instead.
 */
import { render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('@/auth', () => ({ auth: jest.fn() }));
jest.mock('next/navigation', () => ({ redirect: jest.fn() }));

import { auth } from '@/auth';
import { redirect } from 'next/navigation';
import HomePage, { metadata } from '@/app/page';
import { COMPANY } from '@/lib/legal/company';
import { PERIOD, PLANS, limitLabel, priceLabel } from '@/lib/billing/plans';
import { WORKFLOW_STAGES } from '@/lib/types/workflow';

const mockAuth = auth as unknown as jest.Mock;
const mockRedirect = redirect as unknown as jest.Mock;

async function renderLanding() {
  mockAuth.mockResolvedValue(null);
  render(await HomePage());
}

beforeEach(() => {
  mockAuth.mockReset();
  mockRedirect.mockReset();
});

describe('signed in', () => {
  it('keeps the dashboard redirect', async () => {
    mockAuth.mockResolvedValue({ user: { email: 'someone@example.com' } });
    await HomePage();
    expect(mockRedirect).toHaveBeenCalledWith('/dashboard');
  });

  it('shows the landing page to an anonymous visitor and redirects no one', async () => {
    await renderLanding();
    expect(mockRedirect).not.toHaveBeenCalled();
  });
});

describe('hero', () => {
  it('states the one value line as the page heading', async () => {
    await renderLanding();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(COMPANY.valueLine);
  });

  it('shows the wordmark under the product name', async () => {
    await renderLanding();
    expect(screen.getByRole('img', { name: COMPANY.serviceName })).toBeInTheDocument();
  });

  it('has one primary call to action, to sign-in (open OAuth signup, D3)', async () => {
    await renderLanding();
    const hero = screen.getByRole('heading', { level: 1 }).closest('section')!;
    expect(within(hero).getByRole('link', { name: /get started/i })).toHaveAttribute('href', '/auth/signin');
  });

  it('sets the page title and canonical address', () => {
    expect(JSON.stringify(metadata.title)).toMatch(/Explained predictions from your spreadsheet/);
    expect(metadata.alternates?.canonical).toBe('/');
  });
});

describe('proof points', () => {
  it('has the three from the positioning document', async () => {
    await renderLanding();
    const section = screen.getByRole('region', { name: /why it holds up/i });
    expect(within(section).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Validated, not vibes',
      'Explained and reproducible',
      'Safe with real data',
    ]);
  });
});

describe('how it works', () => {
  it('lists every workflow stage, in order, under the name the app uses', async () => {
    await renderLanding();
    const section = screen.getByRole('region', { name: /how it works/i });
    const items = within(section).getAllByRole('listitem');
    expect(items).toHaveLength(WORKFLOW_STAGES.length);
    WORKFLOW_STAGES.forEach((stage, i) => {
      expect(items[i]).toHaveTextContent(stage.name);
    });
  });
});

describe('pricing summary', () => {
  it('shows each tier with the price and training-run limit from the shared plan source', async () => {
    await renderLanding();
    const section = screen.getByRole('region', { name: /pricing/i });
    for (const plan of PLANS) {
      const card = within(section).getByRole('heading', { name: plan.name }).closest('li')!;
      expect(card).toHaveTextContent(priceLabel(plan));
      expect(card).toHaveTextContent(`${limitLabel(plan.limits.training_runs)} training runs per ${PERIOD}`);
    }
  });

  it('links to the full table', async () => {
    await renderLanding();
    const section = screen.getByRole('region', { name: /pricing/i });
    expect(within(section).getByRole('link', { name: /full pricing/i })).toHaveAttribute('href', '/pricing');
  });
});

describe('trust strip', () => {
  it('states the four commitments, the refund window from COMPANY', async () => {
    await renderLanding();
    const section = screen.getByRole('region', { name: /your data/i });
    const text = section.textContent ?? '';
    expect(text).toMatch(/PII is scanned and masked before anything reaches a language model/i);
    expect(text).toMatch(/works without an AI key/i);
    expect(text).toMatch(/one-click erasure/i);
    expect(text).toContain(`${COMPANY.refundWindowDays}-day refund`);
  });
});

describe('what it does not do yet', () => {
  it('names the limits a buyer should know before signing up', async () => {
    await renderLanding();
    const section = screen.getByRole('region', { name: /does not do yet/i });
    expect(section).toHaveTextContent(/CSV or XLSX/);
    expect(section).toHaveTextContent(/100 MB/);
    expect(section).toHaveTextContent(/connectors/i);
    expect(section).toHaveTextContent(/joins/i);
  });
});

describe('the do-not-claim list (positioning.md section 6)', () => {
  it('claims none of it', async () => {
    await renderLanding();
    const text = document.body.textContent ?? '';
    const forbidden = [
      /auto-?scal/i,
      /auto-?provision/i,
      /low-latency/i,
      /global (infrastructure|network)/i,
      /per-request/i,
      /ONNX|PMML/,
      /better than ChatGPT/i,
      /replaces your statistics/i,
      /A\/B test/i,
      /recipes/i,
    ];
    for (const pattern of forbidden) expect(text).not.toMatch(pattern);
  });

  it('shows no test account address', async () => {
    await renderLanding();
    expect(document.body.textContent).not.toMatch(/test@/i);
  });
});
