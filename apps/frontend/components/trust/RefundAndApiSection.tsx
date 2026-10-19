import Link from 'next/link'
import { API_BASE_URL } from '@/lib/config'
import { COMPANY } from '@/lib/legal/company'

/** The refund window is `COMPANY.refundWindowDays`, the number the Terms and /pricing state. */
export function RefundSection() {
  return (
    <section aria-labelledby="refunds-heading" id="refunds">
      <h2 id="refunds-heading">Refunds</h2>
      <p>
        If you are not satisfied, email{' '}
        <a href={`mailto:${COMPANY.supportEmail}`}>{COMPANY.supportEmail}</a> within{' '}
        {COMPANY.refundWindowDays} days of your first paid charge and we will refund it in full.
        See the <Link href="/legal/terms#refunds">refund policy</Link>.
      </p>
    </section>
  )
}

/** #512: the published description is the live route table, run against a server in CI. */
export function ApiSection() {
  const spec = `${API_BASE_URL}/docs/openapi.json`
  return (
    <section aria-labelledby="api-heading" id="api">
      <h2 id="api-heading">The API</h2>
      <p>
        The published API description is generated from the routes this instance serves, so it
        cannot describe an endpoint that does not exist, and the rate limits it states are read
        from the settings the server enforces. A test generates the Python client, runs it against
        a live server and calls a documented endpoint. Read it as{' '}
        <a href={spec}>openapi.json</a> or <a href={`${API_BASE_URL}/docs/openapi.yaml`}>YAML</a>.
      </p>
    </section>
  )
}
