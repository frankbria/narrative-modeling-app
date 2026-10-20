import Link from 'next/link'
import {
  AI_SAMPLE_ROWS,
  DATASET_KEY_TEMPLATE,
  MASKED_KEY_TEMPLATE,
  PII_SCAN_SAMPLE_ROWS,
  SUMMARY_EXAMPLE_VALUES,
} from '@/lib/trust/datasetFacts'

/**
 * What the code does with an uploaded file. Each step names its source:
 * `dataset_s3_key` (utils/s3.py), the PII scan (pii_detector.py), `_summary_frame` and
 * `prepare_dataset_summary_from_df` (secure_upload.py, ai_summary.py, #490/#718),
 * `dataset_summarization.py` (the Explore panel). `lib/trust/datasetFacts.ts` holds the
 * figures and `test_trust_page_facts.py` holds them to the code.
 */
export function DatasetSection() {
  return (
    <section aria-labelledby="dataset-heading" id="dataset">
      <h2 id="dataset-heading">What happens to a dataset</h2>
      <ol>
        <li>
          <strong>It is stored under your account.</strong> The file is written to AWS S3 at{' '}
          <code>{DATASET_KEY_TEMPLATE}</code>, where the extension is the one on your file. If you
          choose to mask personal values on upload, the stored copy is a CSV at{' '}
          <code>{MASKED_KEY_TEMPLATE}</code>. The name you gave the file is not part of the key.
        </li>
        <li>
          <strong>It is scanned for personal data.</strong> Files uploaded on the Upload page are
          checked column by column. The column name is matched against common names for an email
          address, phone number, social security number, person&apos;s name, address, date of
          birth, medical record id and financial account. The first {PII_SCAN_SAMPLE_ROWS}{' '}
          non-empty values are matched against patterns for email addresses, phone numbers, social
          security numbers, card numbers and IP addresses. The scan is a heuristic and reads a
          sample of each column, so it can miss personal data that is not in the first{' '}
          {PII_SCAN_SAMPLE_ROWS} values.
        </li>
        <li>
          <strong>A high-risk finding stops the upload until you confirm it,</strong> at any
          file size. You then choose whether the stored copy has its personal values masked.
        </li>
        <li>
          <strong>What the AI summary receives.</strong> After an upload, OpenAI is sent the file
          name, the row and column counts, each column&apos;s name, type and counts of unique and
          missing values, and up to {SUMMARY_EXAMPLE_VALUES}{' '}example values per column. When the
          scan flags a column, its example values are redacted first, each replaced by a numbered
          placeholder, whether or not you chose to mask the stored copy. The file name, and the example values
          of columns the scan did not flag, are sent as they are. The AI Insights panel on the
          Explore page sends up to {AI_SAMPLE_ROWS}{' '}sample rows; see{' '}
          <Link href="/legal/privacy#ai-features">section 5 of the Privacy Policy</Link>.
        </li>
        <li>
          <strong>Trained models are signed.</strong> A model file is signed when it is saved and
          verified before it is loaded; a file that fails verification is refused.
        </li>
      </ol>
    </section>
  )
}
