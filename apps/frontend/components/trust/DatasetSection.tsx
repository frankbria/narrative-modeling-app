import Link from 'next/link'
import { AI_SAMPLE_ROWS, DATASET_KEY_PREFIX, PII_SCAN_SAMPLE_ROWS } from '@/lib/trust/datasetFacts'

/**
 * What the code does with an uploaded file. Each step names its source:
 * `dataset_s3_key` (utils/s3.py), the PII scan and `_summary_frame`
 * (secure_upload.py, #490/#718), `dataset_summarization.py` (the sample rows).
 * `__tests__/test_security/test_trust_page_facts.py` holds the figures to the code.
 */
export function DatasetSection() {
  return (
    <section aria-labelledby="dataset-heading" id="dataset">
      <h2 id="dataset-heading">What happens to a dataset</h2>
      <ol>
        <li>
          <strong>It is stored under your account.</strong> The file is written to AWS S3 at{' '}
          <code>{DATASET_KEY_PREFIX}/&lt;your account id&gt;/&lt;random id&gt;</code>. The name you
          gave the file is not part of that key, so two accounts uploading <code>data.csv</code>{' '}
          never share a path.
        </li>
        <li>
          <strong>It is scanned for personal data.</strong> Files uploaded on the Upload page are
          checked column by column: the column name, and the first {PII_SCAN_SAMPLE_ROWS} non-empty
          values, against patterns for email addresses, phone numbers, social security numbers, card
          numbers and IP addresses. The scan is a heuristic. It reads a sample of each column, so
          it can miss personal data that is not in the first {PII_SCAN_SAMPLE_ROWS} values.
        </li>
        <li>
          <strong>A high-risk finding stops the upload until you confirm it.</strong> You then
          choose whether the stored copy has its personal values masked.
        </li>
        <li>
          <strong>What the AI summary receives.</strong> When the scan flags a column, the summary
          written after the upload is built from a copy in which every value of that column is
          redacted, whether or not you chose to mask the stored copy. When nothing is flagged, the
          model receives your column names and up to {AI_SAMPLE_ROWS} sample rows as they are. The
          other AI panels send what{' '}
          <Link href="/legal/privacy#ai-features">section 5 of the Privacy Policy</Link> lists.
        </li>
        <li>
          <strong>Trained models are signed.</strong> A model file is signed when it is saved and
          verified before it is loaded; a file that fails verification is refused.
        </li>
      </ol>
    </section>
  )
}
