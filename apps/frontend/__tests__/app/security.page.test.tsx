/**
 * Public /security page (#772 AC1).
 *
 * Every figure comes from a source the backend suite holds to the code
 * (`lib/trust/datasetFacts.ts`, `SUB_PROCESSORS`, `COMPANY`); the sub-processor
 * table is rendered from `SUB_PROCESSORS` exactly as the privacy policy renders it.
 */
import { render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import SecurityPage, { metadata } from '@/app/security/page'
import { COMPANY, SUB_PROCESSORS } from '@/lib/legal/company'
import {
  AI_SAMPLE_ROWS,
  DATASET_KEY_TEMPLATE,
  MASKED_KEY_TEMPLATE,
  PII_NAME_CATEGORIES,
  PII_SCAN_SAMPLE_ROWS,
  PII_VALUE_CATEGORIES,
  SUMMARY_EXAMPLE_VALUES,
} from '@/lib/trust/datasetFacts'

function section(name: RegExp): HTMLElement {
  return screen.getByRole('region', { name })
}

describe('Security page', () => {
  it('has one h1 and page metadata with a canonical address', () => {
    render(<SecurityPage />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/security/i)
    expect(String(metadata.title)).toContain(COMPANY.serviceName)
    expect(metadata.description).toBeTruthy()
    expect(metadata.alternates?.canonical).toBe('/security')
  })

  // complete_chunked_upload holds a high-risk file for confirmation too (#1122).
  it('says a high-risk finding stops the upload at any file size', () => {
    render(<SecurityPage />)
    expect(screen.getByText(/A high-risk finding stops the upload until you confirm it/)).toBeInTheDocument()
    expect(screen.queryByText(/stored as uploaded/)).not.toBeInTheDocument()
  })

  it('says where a dataset is stored: under the account prefix, in S3', () => {
    render(<SecurityPage />)
    const text = section(/what happens to a dataset/i).textContent ?? ''
    expect(text).toContain(DATASET_KEY_TEMPLATE)
    expect(text).toContain(MASKED_KEY_TEMPLATE)
    expect(text).toMatch(/AWS S3/)
  })

  it('says the column-name check covers more categories than the value patterns', () => {
    render(<SecurityPage />)
    const text = section(/what happens to a dataset/i).textContent ?? ''
    expect(PII_NAME_CATEGORIES.length).toBeGreaterThan(PII_VALUE_CATEGORIES.length)
    expect(text).toMatch(/date of birth/i)
    expect(text).toMatch(/medical/i)
    expect(text).toMatch(/financial account/i)
    expect(text).toMatch(/card numbers/i)
  })

  it('says exactly what the upload summary sends: file name, counts, example values per column', () => {
    render(<SecurityPage />)
    const text = section(/what happens to a dataset/i).textContent ?? ''
    expect(text).toMatch(/file name/i)
    expect(text).toContain(`up to ${SUMMARY_EXAMPLE_VALUES} example values per column`)
  })

  it('states the PII scan with its real sample size, and what the AI summary receives', () => {
    render(<SecurityPage />)
    const text = section(/what happens to a dataset/i).textContent ?? ''
    expect(text).toContain(`first ${PII_SCAN_SAMPLE_ROWS}`)
    expect(text).toMatch(/redact/i)
    expect(text).toContain(`up to ${AI_SAMPLE_ROWS} sample rows`)
  })

  it('says nothing about backups (#299 is not done)', () => {
    render(<SecurityPage />)
    expect(document.body.textContent).not.toMatch(/backup|snapshot/i)
  })

  it('renders every sub-processor from the one source, each with its privacy link', () => {
    render(<SecurityPage />)
    const table = within(section(/sub-processors/i)).getByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(SUB_PROCESSORS.length)
    SUB_PROCESSORS.forEach((processor, i) => {
      expect(rows[i]).toHaveTextContent(processor.purpose)
      expect(within(rows[i]).getByRole('link', { name: processor.name })).toHaveAttribute(
        'href',
        processor.privacyUrl,
      )
    })
  })

  it('gives erasure and retention as the privacy policy does, and links to it', () => {
    render(<SecurityPage />)
    const retention = section(/erasure and retention/i)
    expect(retention).toHaveTextContent(/do not expire/i)
    expect(within(retention).getByRole('link', { name: /privacy policy/i })).toHaveAttribute(
      'href',
      '/legal/privacy#retention',
    )
    expect(retention).toHaveTextContent(COMPANY.privacyEmail)
  })

  it('says deleting a dataset removes the models trained on it, as the privacy policy does (#1111)', () => {
    render(<SecurityPage />)
    const retention = section(/erasure and retention/i)
    expect(retention).toHaveTextContent(/models trained on it with their saved files/i)
    expect(retention).not.toHaveTextContent(/separate objects/i)
  })

  it('states the refund window from COMPANY and links the refund terms', () => {
    render(<SecurityPage />)
    const refunds = section(/refunds/i)
    expect(refunds).toHaveTextContent(`${COMPANY.refundWindowDays} days`)
    expect(within(refunds).getByRole('link', { name: /refund policy/i })).toHaveAttribute(
      'href',
      '/legal/terms#refunds',
    )
  })

  it('links the published API description, which is the live route table (#512)', () => {
    render(<SecurityPage />)
    const api = section(/api/i)
    expect(within(api).getByRole('link', { name: /openapi\.json/i })).toHaveAttribute(
      'href',
      expect.stringMatching(/\/api\/v1\/docs\/openapi\.json$/),
    )
  })

  it('claims none of the do-not-claim list and shows no test address', () => {
    render(<SecurityPage />)
    const text = document.body.textContent ?? ''
    for (const pattern of [/auto-?scal/i, /SOC ?2/i, /ISO ?27001/i, /HIPAA/i, /GDPR[- ]compliant/i, /test@/i]) {
      expect(text).not.toMatch(pattern)
    }
  })
})
