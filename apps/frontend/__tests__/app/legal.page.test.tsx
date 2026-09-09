/**
 * Terms of Service and Privacy Policy pages (issue #473).
 *
 * These are compliance surfaces, so the assertions are written against the
 * things that make them compliant rather than against prose: the named
 * sub-processors (a template that omits OpenAI is the specific failure the
 * issue calls out), a refund/cancellation section Stripe can find, stated
 * retention periods, and a deletion promise no stronger than what the code
 * actually performs.
 */

import { render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import TermsPage from '@/app/legal/terms/page';
import PrivacyPage from '@/app/legal/privacy/page';
import { COMPANY, SUB_PROCESSORS } from '@/lib/legal/company';

describe('Terms of Service', () => {
  it('names the contracting entity', () => {
    render(<TermsPage />);
    expect(screen.getByRole('heading', { level: 1, name: /terms of service/i })).toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(COMPANY.legalEntity, 'i')).length).toBeGreaterThan(0);
  });

  it('carries an addressable refund and cancellation section (AC2)', () => {
    render(<TermsPage />);
    const heading = screen.getByRole('heading', { name: /refunds and cancellation/i });
    // Stripe reviewers are pointed at a deep link, so the section must be anchorable.
    expect(heading.closest('section')).toHaveAttribute('id', 'refunds');
  });

  it('states the 14-day money-back window and the no-proration rule after it', () => {
    render(<TermsPage />);
    const section = screen.getByRole('heading', { name: /refunds and cancellation/i }).closest('section')!;
    expect(within(section).getByText(/14 days/i)).toBeInTheDocument();
    expect(within(section).getByText(/not prorated|no prorated|without a prorated/i)).toBeInTheDocument();
  });

  it('covers acceptable use, availability, liability and termination (AC1)', () => {
    render(<TermsPage />);
    for (const name of [/acceptable use/i, /service availability/i, /limitation of liability/i, /termination/i]) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument();
    }
  });

  it('states the governing law the founder chose', () => {
    render(<TermsPage />);
    expect(screen.getByText(new RegExp(COMPANY.governingLaw, 'i'))).toBeInTheDocument();
  });

  it('links to the Privacy Policy', () => {
    render(<TermsPage />);
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute('href', '/legal/privacy');
  });
});

describe('Privacy Policy', () => {
  it('names every sub-processor, OpenAI included (AC3)', () => {
    render(<PrivacyPage />);
    // The list is non-trivial and the issue's central risk is an omission, so
    // assert the whole set rather than a sample.
    expect(SUB_PROCESSORS.map((p) => p.name)).toEqual(
      expect.arrayContaining(['AWS S3', 'MongoDB Atlas', 'OpenAI', 'Stripe', 'Google', 'GitHub']),
    );
    for (const processor of SUB_PROCESSORS) {
      expect(screen.getByRole('cell', { name: processor.name })).toBeInTheDocument();
      expect(screen.getByText(processor.purpose)).toBeInTheDocument();
    }
  });

  it('discloses that dataset rows themselves are sent to OpenAI', () => {
    render(<PrivacyPage />);
    const openai = SUB_PROCESSORS.find((p) => p.name === 'OpenAI')!;
    // dataset_summarization.py sends up to 5 sample rows; a policy that says
    // only "AI features" would understate what leaves our infrastructure.
    expect(openai.purpose).toMatch(/sample rows/i);
  });

  it('states retention periods including the backup window (AC4)', () => {
    render(<PrivacyPage />);
    const section = screen.getByRole('heading', { name: /retention/i }).closest('section')!;
    expect(within(section).getByText(/35 days/i)).toBeInTheDocument();
    // Asserted on the section text rather than a single node: "Backups" is both
    // a list-item label and a word in the sentence, so a node query is ambiguous.
    expect(section.textContent).toMatch(/backup/i);
  });

  it('does not promise deletion the erasure cascade does not perform (AC4)', () => {
    const { container } = render(<PrivacyPage />);
    const text = (container.textContent ?? '').replace(/\s+/g, ' ');

    // #497: the cascade misses trained models and their S3 artifacts, AND reports
    // success anyway. Three claims therefore have to stay off this page, each
    // phrased the way it would actually be written back in:
    expect(text).not.toMatch(/all data we hold for you/i); // unqualified completeness
    expect(text).not.toMatch(/tell you what was removed/i); // an itemised accounting the manifest cannot back
    expect(text).not.toMatch(/(permanently|immediately) delete (all|everything)/i);

    // And the qualifications that make the remaining promise true have to stay ON
    // it — a blanket rewrite would drop these, which the negatives alone miss.
    expect(text).toMatch(/deleting a dataset does not delete the models/i);
    expect(text).toMatch(/records the self-service delete actions do not reach/i);
    expect(
      within(screen.getByRole('heading', { name: /retention/i }).closest('section')!)
        .getByText(/invoices and payment records/i),
    ).toBeInTheDocument();

    expect(screen.getByRole('link', { name: new RegExp(COMPANY.privacyEmail, 'i') })).toHaveAttribute(
      'href',
      `mailto:${COMPANY.privacyEmail}`,
    );
  });

  it('records the cookie decision rather than deferring it (AC6)', () => {
    render(<PrivacyPage />);
    const section = screen.getByRole('heading', { name: /cookies/i }).closest('section')!;
    expect(within(section).getByText(/no analytics|no advertising|strictly necessary/i)).toBeInTheDocument();
  });

  // Guards a source-level typo only: a dropped space around an interpolated
  // constant reads as "Narrative Modeling Appservice" in a document customers
  // read closely. It does NOT catch the server-render variant of the same
  // defect — two interpolations on one JSX line lose the space after the second
  // in the RSC output while rendering fine here — which is why both pages use an
  // explicit {' '} after every interpolation followed by prose.
  it.each([
    ['Terms', TermsPage],
    ['Privacy', PrivacyPage],
  ])('%s prose has no words glued to an interpolated constant', (_label, Page) => {
    const { container } = render(<Page />);
    const text = (container.textContent ?? '').replace(/\s+/g, ' ');
    expect(text).toContain(`${COMPANY.serviceName} service`);
    expect(text).toContain(`${COMPANY.legalEntity} `);
  });

  it('links to the Terms', () => {
    render(<PrivacyPage />);
    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute('href', '/legal/terms');
  });
});
