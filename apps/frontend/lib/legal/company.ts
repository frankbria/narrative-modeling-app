/**
 * Single source of truth for the identity and disclosure facts the legal pages
 * publish (issue #473).
 *
 * These are founder decisions, not implementation details — the entity, the
 * governing law and the refund window were chosen deliberately. Change them
 * here and both pages follow; the page tests read the same constants, so a
 * change that contradicts a stated fact fails rather than silently shipping.
 *
 * The sub-processor list is a legal claim about where customer data actually
 * goes, so each entry is traceable to code:
 *   AWS S3          app/services/s3_service.py
 *   MongoDB Atlas   app/main.py (Beanie/Motor)
 *   OpenAI          app/services/dataset_summarization.py:129 (5 sample rows)
 *   Stripe          app/api/routes/billing.py
 *   Google/GitHub   apps/frontend/auth.ts
 * Redis is deliberately absent: it runs on our own infrastructure, so it is a
 * hosting component rather than a third party receiving customer data.
 */

export const COMPANY = {
  /** Product name as it appears to users. */
  serviceName: 'Narrative Modeling App',
  /** The contracting party. */
  legalEntity: 'Noaysk Enterprises, LLC, dba Bria Strategy Group',
  governingLaw: 'State of Arizona, USA',
  privacyEmail: 'privacy@briaanalytics.com',
  supportEmail: 'support@briaanalytics.com',
  /** Money-back window on a customer's first paid charge, in days. */
  refundWindowDays: 14,
  /**
   * Longest a deleted record can survive in backups: Atlas keeps weekly
   * snapshots for 4 weeks and S3 purges noncurrent versions at 30 days
   * (docs/deployment/DATA_ERASURE_AND_BACKUP_RUNBOOK.md), so 35 days is the
   * honest ceiling rather than a round number.
   */
  backupHorizonDays: 35,
  effectiveDate: 'September 9, 2026',
} as const

export interface SubProcessor {
  name: string
  purpose: string
  privacyUrl: string
}

export const SUB_PROCESSORS: readonly SubProcessor[] = [
  {
    name: 'AWS S3',
    purpose: 'Stores your uploaded dataset files and trained model artifacts.',
    privacyUrl: 'https://aws.amazon.com/privacy/',
  },
  {
    name: 'MongoDB Atlas',
    purpose: 'Stores your account record, dataset metadata, and job history.',
    privacyUrl: 'https://www.mongodb.com/legal/privacy-policy',
  },
  {
    name: 'OpenAI',
    purpose:
      'Generates dataset summaries, feature suggestions and result explanations. Receives your column names and up to five sample rows of the dataset being analysed.',
    privacyUrl: 'https://openai.com/policies/privacy-policy',
  },
  {
    name: 'Stripe',
    purpose: 'Processes subscription payments and holds your billing details.',
    privacyUrl: 'https://stripe.com/privacy',
  },
  {
    name: 'Google',
    purpose: 'Authenticates you if you sign in with Google. Receives no dataset content.',
    privacyUrl: 'https://policies.google.com/privacy',
  },
  {
    name: 'GitHub',
    purpose: 'Authenticates you if you sign in with GitHub. Receives no dataset content.',
    privacyUrl: 'https://docs.github.com/en/site-policy/privacy-policies',
  },
]
