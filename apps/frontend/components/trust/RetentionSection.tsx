import Link from 'next/link'
import { COMPANY } from '@/lib/legal/company'

/**
 * Erasure and retention as app/legal/privacy section 6 states them, never stronger
 * (`erasure_service.py`, docs/ops/DATA_ERASURE_AND_BACKUP_RUNBOOK.md section 1).
 */
export function RetentionSection() {
  return (
    <section aria-labelledby="retention-heading" id="retention">
      <h2 id="retention-heading">Erasure and retention</h2>
      <ul>
        <li>
          <strong>We do not expire your data automatically.</strong> Datasets, models and their
          derived records stay until you remove them or your account is closed.
        </li>
        <li>
          <strong>Deleting a dataset</strong> removes the uploaded file and the analysis records
          tied to it. Trained models are separate objects with their own delete action.
        </li>
        <li>
          <strong>Deleting everything:</strong> email{' '}
          <a href={`mailto:${COMPANY.privacyEmail}`}>{COMPANY.privacyEmail}</a>. We action these
          within 30 days. Each erasure leaves an append-only log entry recording that it happened,
          who asked and when, not the data that was deleted, and invoices are kept for as long as
          tax law requires.
        </li>
      </ul>
      <p>
        The full wording is in the <Link href="/legal/privacy#retention">Privacy Policy</Link>.
      </p>
    </section>
  )
}
