import type { Metadata } from 'next'
import Link from 'next/link'
import { COMPANY, SUB_PROCESSORS } from '@/lib/legal/company'

export const metadata: Metadata = {
  title: `Privacy Policy | ${COMPANY.serviceName}`,
  description: `What ${COMPANY.serviceName} collects, which sub-processors receive it, how long it is kept, and how to have it deleted.`,
}

export default function PrivacyPage() {
  return (
    <>
      <h1>Privacy Policy</h1>
      <p className="lead">
        Effective {COMPANY.effectiveDate}. This explains what the {COMPANY.serviceName}{' '}
        service collects, who else sees it, and how long we keep it. It sits alongside our{' '}
        <Link href="/legal/terms">Terms of Service</Link>.
      </p>

      <section id="scope">
        <h2>1. Who we are</h2>
        <p>
          {COMPANY.legalEntity} operates the {COMPANY.serviceName}{' '}
          service and is the controller of the personal data described here. Where you upload a
          dataset containing other people&rsquo;s personal data, you are the controller of that
          data and we process it on your behalf.
        </p>
      </section>

      <section id="what-we-collect">
        <h2>2. What we collect</h2>
        <ul>
          <li>
            <strong>Account data</strong> — the name, email address and profile image your Google or
            GitHub account releases to us when you sign in, plus the API keys you create.
          </li>
          <li>
            <strong>Datasets you upload</strong> — the files themselves and everything derived from
            them: inferred schemas, column statistics, transformations, versions, trained models and
            prediction results. We do not inspect or restrict what is in them, so whether they
            contain personal data is your decision.
          </li>
          <li>
            <strong>Usage records</strong> — the counts we meter for quotas (uploads, training runs,
            predictions), job status and timestamps, and server logs containing request paths, IP
            addresses and error details.
          </li>
          <li>
            <strong>Billing data</strong> — your subscription tier and status. Card details go
            directly to Stripe; we never see or store them.
          </li>
        </ul>
      </section>

      <section id="how-we-use">
        <h2>3. How we use it, and on what basis</h2>
        <p>
          We use account and dataset data to provide the service you asked for — storing your files,
          running analyses and training the models you request (performance of our contract with
          you). We use usage records and logs to enforce quotas, keep the service secure and debug
          failures (our legitimate interest in running a reliable service). We use billing data to
          take payment and meet our accounting obligations (contract and legal obligation).
        </p>
        <p>
          We do not sell or share your personal data for advertising, and we do not use your
          datasets to train our own models. No automated decision producing legal effects about you
          is made by us; models you train are yours, and how you use them is your responsibility.
        </p>
      </section>

      <section id="sub-processors">
        <h2>4. Sub-processors</h2>
        <p>
          Running the service means these third parties process data on our behalf. Each is bound by
          a data-processing agreement and may only use the data to provide their service to us.
        </p>
        <table>
          <thead>
            <tr>
              <th scope="col">Sub-processor</th>
              <th scope="col">What it does with your data</th>
            </tr>
          </thead>
          <tbody>
            {SUB_PROCESSORS.map((processor) => (
              <tr key={processor.name}>
                <td className="whitespace-nowrap">
                  <a href={processor.privacyUrl} target="_blank" rel="noopener noreferrer">
                    {processor.name}
                  </a>
                </td>
                <td>{processor.purpose}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          We will update this list before adding a new sub-processor that receives dataset content.
        </p>
      </section>

      <section id="ai-features">
        <h2>5. What the AI features send to OpenAI</h2>
        <p>
          This is the disclosure most people care about, so it gets its own section. When you use a
          dataset summary, an AI insight, a feature suggestion or a result explanation, we send
          OpenAI a description of your dataset: its column names, inferred types, summary statistics,
          and up to five rows sampled from the file. If those rows contain personal data, that
          personal data leaves our infrastructure.
        </p>
        <p>
          These features are optional in the sense that the rest of the product works without them,
          and the service runs with the AI features disabled when no API key is configured. If you
          do not want dataset content sent to OpenAI, do not use the AI panels — or tell us at{' '}
          {COMPANY.privacyEmail}{' '}
          and we will disable them for your account.
        </p>
      </section>

      <section id="retention">
        <h2>6. Retention and deletion</h2>
        <p>
          We do not expire your data automatically. Datasets, models and their derived records stay
          until you remove them or your account is closed.
        </p>
        <ul>
          <li>
            <strong>Deleting a dataset</strong> removes the uploaded file and the analysis records
            tied to it. Trained models are separate objects with their own delete action — deleting
            a dataset does not delete the models you trained from it, so delete those too if you
            want them gone.
          </li>
          <li>
            <strong>Deleting everything</strong> — email {COMPANY.privacyEmail}{' '}
            and we will erase the data we hold for you, including records the self-service delete
            actions do not reach. We action these within 30 days, and the categories listed below
            are retained afterwards. Ask us to confirm a specific dataset or model has been removed
            and we will check it individually.
          </li>
          <li>
            <strong>Backups</strong> — database snapshots (hourly for two days, daily for a week,
            weekly for four weeks) and versioned file storage mean a deleted record can survive in
            backups for up to {COMPANY.backupHorizonDays}{' '}
            days after deletion, after which it is purged. We do not use these copies for anything
            other than disaster recovery.
          </li>
          <li>
            <strong>What we keep afterwards</strong> — invoices and payment records for as long as
            tax and accounting law requires, and an append-only erasure log recording that a
            deletion happened, who asked for it and when. The log records the event, not the data
            that was deleted.
          </li>
        </ul>
      </section>

      <section id="your-rights">
        <h2>7. Your rights</h2>
        <p>
          Depending on where you live you may have the right to access, correct, export, delete or
          restrict processing of your personal data, to object to processing based on legitimate
          interests, and to withdraw consent. California residents additionally have the right to
          know what is collected and to not be discriminated against for exercising these rights; we
          do not sell or share personal information as those terms are defined by the CCPA.
        </p>
        <p>
          Email {COMPANY.privacyEmail}{' '}
          to exercise any of these. We respond within 30 days and do not
          charge for it. If you are in the EU, UK or EEA and are unsatisfied with our response, you
          may complain to your local supervisory authority.
        </p>
      </section>

      <section id="cookies">
        <h2>8. Cookies</h2>
        <p>
          We set strictly necessary cookies only: the session cookie that keeps you signed in and the
          CSRF token that protects the sign-in flow. There are no analytics, advertising or
          cross-site tracking cookies, which is why you see no consent banner.
        </p>
        <p>
          If we ever add analytics, we will add a consent mechanism before turning it on and update
          this section.
        </p>
      </section>

      <section id="security">
        <h2>9. Security</h2>
        <p>
          Data is encrypted in transit and at rest in our storage providers. Access is scoped per
          account: dataset, model and version records are keyed to their owner and checked on every
          request. Model artifacts are signed and verified before being loaded. Internal access to
          production is limited to the people who operate the service.
        </p>
        <p>
          No service is immune to breach. If one occurs affecting your personal data, we will notify
          affected account holders and any regulator we are required to notify, without undue delay.
        </p>
      </section>

      <section id="transfers">
        <h2>10. International transfers</h2>
        <p>
          Our infrastructure and our sub-processors are primarily in the United States. If you are in
          the EU, UK or EEA, using the service transfers your data there, relying on the Standard
          Contractual Clauses (and the UK Addendum where relevant) in our agreements with those
          providers.
        </p>
      </section>

      <section id="children">
        <h2>11. Children</h2>
        <p>
          The service is not intended for anyone under 16, and we do not knowingly collect their
          personal data. Tell us if you believe a child has created an account and we will remove it.
        </p>
      </section>

      <section id="changes">
        <h2>12. Changes and contact</h2>
        <p>
          We will notify account holders before a change that materially affects how we handle
          personal data takes effect. For anything in this policy, including a data request, contact{' '}
          <a href={`mailto:${COMPANY.privacyEmail}`}>{COMPANY.privacyEmail}</a>.
        </p>
      </section>
    </>
  )
}
