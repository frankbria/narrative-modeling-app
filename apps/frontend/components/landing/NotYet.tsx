import { COMPANY } from '@/lib/legal/company'

/** Positioning.md section 6: a rigor product says what it does not do, and filters the wrong buyer. */
const LIMITS = [
  'Files are CSV or XLSX, up to 100 MB.',
  'No database or cloud-storage connectors.',
  'No multi-file joins.',
]

export function NotYet() {
  const limits = LIMITS
  return (
    <section aria-labelledby="notyet-heading" className="space-y-3">
      <h2 id="notyet-heading" className="text-2xl font-semibold text-foreground">
        {`What ${COMPANY.serviceName} does not do yet`}
      </h2>
      <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
        {limits.map((limit) => (
          <li key={limit}>{limit}</li>
        ))}
      </ul>
    </section>
  )
}
