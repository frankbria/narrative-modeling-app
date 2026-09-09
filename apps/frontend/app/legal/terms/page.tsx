import type { Metadata } from 'next'
import Link from 'next/link'
import { COMPANY } from '@/lib/legal/company'

export const metadata: Metadata = {
  title: `Terms of Service | ${COMPANY.serviceName}`,
  description: `The terms governing use of the hosted ${COMPANY.serviceName} service, including the refund and cancellation policy.`,
}

export default function TermsPage() {
  return (
    <>
      <h1>Terms of Service</h1>
      <p className="lead">
        Effective {COMPANY.effectiveDate}. These terms govern the hosted {COMPANY.serviceName}{' '}
        service. See also our{' '}
        <Link href="/legal/privacy">Privacy Policy</Link>, which explains what we do with the data
        you upload.
      </p>

      <section id="agreement">
        <h2>1. Who you are contracting with</h2>
        <p>
          The {COMPANY.serviceName} service is operated by {COMPANY.legalEntity}{' '}
          (&ldquo;we&rdquo;, &ldquo;us&rdquo;). By creating an account or using the
          service you agree to these terms. If you are agreeing on behalf of an organisation, you
          confirm you are authorised to bind it.
        </p>
        <p>
          The software behind this service is published under the GNU AGPL v3, and you may run your
          own copy under that licence. These terms apply only to the hosted service we operate.
        </p>
      </section>

      <section id="accounts">
        <h2>2. Accounts and access</h2>
        <p>
          Accounts are personal and are created through Google or GitHub sign-in. You are
          responsible for activity under your account and for keeping any API keys you generate
          secret. Access to the service is currently invite-based; we may grant, decline or revoke
          invitations at our discretion.
        </p>
      </section>

      <section id="acceptable-use">
        <h2>3. Acceptable use</h2>
        <p>You agree not to use the service to:</p>
        <ul>
          <li>
            upload data you do not have the right to process, or special-category personal data
            (health, biometric, precise location, and similar) without a lawful basis for doing so;
          </li>
          <li>
            build or deploy models intended to make automated decisions about individuals in ways
            prohibited by applicable law, or to identify individuals who expect to remain anonymous;
          </li>
          <li>
            attempt to circumvent quotas, rate limits, tenant isolation or authentication, or to
            access another customer&rsquo;s data;
          </li>
          <li>
            upload malware, or run workloads whose purpose is to consume capacity rather than to
            analyse your own data;
          </li>
          <li>resell or sublicense access to the hosted service without our written agreement.</li>
        </ul>
        <p>
          We may suspend an account that is causing harm to the service or to other customers, and
          will tell you why when we do.
        </p>
      </section>

      <section id="your-data">
        <h2>4. Your data</h2>
        <p>
          You keep ownership of everything you upload and of the models you train. You grant us only
          the permission needed to run the service for you: to store, process, transmit and display
          your data, and to send the limited extracts described in the Privacy Policy to the
          sub-processors listed there so that the AI features work.
        </p>
        <p>
          We do not use your datasets to train our own models, and we do not sell your data. If you
          delete a dataset we stop processing it, subject to the deletion timelines set out in the
          Privacy Policy.
        </p>
      </section>

      <section id="plans">
        <h2>5. Plans, quotas and billing</h2>
        <p>
          Paid plans are billed monthly in advance through Stripe. Each plan carries usage quotas —
          uploads, training runs and predictions — which are enforced in the product; a request that
          would exceed your quota is declined rather than charged as an overage. Prices and quotas
          may change with at least 30 days&rsquo; notice, taking effect at your next renewal.
        </p>
        <p>
          Taxes, where applicable, are added at checkout. A failed payment may lead to your plan
          being downgraded to the free tier until it is resolved.
        </p>
      </section>

      <section id="refunds">
        <h2>6. Refunds and cancellation</h2>
        <p>
          You can cancel at any time from the billing page in your account settings, which opens the
          Stripe customer portal. Cancellation takes effect at the end of the period you have
          already paid for, and you keep access until then.
        </p>
        <p>
          If you are not satisfied, email {COMPANY.supportEmail} within {COMPANY.refundWindowDays}{' '}
          days of your first paid charge and we will refund it in full.
        </p>
        <p>
          After that window, cancelling stops future charges but the current period is not prorated
          or refunded. We may make exceptions — for example where a fault on our side prevented you
          from using what you paid for.
        </p>
      </section>

      <section id="availability">
        <h2>7. Service availability</h2>
        <p>
          The service is provided on an &ldquo;as is&rdquo; and &ldquo;as available&rdquo; basis. We
          do not currently offer a contractual uptime commitment or service credits. We do maintain
          backups, and we will give reasonable advance notice of planned maintenance that we expect
          to interrupt the service.
        </p>
        <p>
          Model training and prediction are statistical processes. Their outputs are not advice, and
          you are responsible for validating any model before you rely on it for a decision.
        </p>
      </section>

      <section id="liability">
        <h2>8. Limitation of liability</h2>
        <p>
          To the fullest extent permitted by law, we are not liable for indirect, incidental,
          special or consequential damages, for lost profits or revenue, or for loss of data beyond
          our obligation to maintain the backups described in the Privacy Policy.
        </p>
        <p>
          Our total liability arising out of or relating to the service is limited to the amount you
          paid us in the twelve months before the event giving rise to the claim, or one hundred US
          dollars if you paid us nothing. Nothing here limits liability that cannot be limited by
          law.
        </p>
      </section>

      <section id="termination">
        <h2>9. Termination</h2>
        <p>
          You may stop using the service and delete your data at any time. We may terminate or
          suspend an account for a material breach of these terms, for non-payment, or if we
          discontinue the service.
        </p>
        <p>
          Unless the law requires otherwise, we will give you at least 30 days to export your data
          before terminating for a reason other than a serious breach or non-payment. After
          termination, your data is deleted on the timeline set out in the Privacy Policy.
        </p>
      </section>

      <section id="changes">
        <h2>10. Changes to these terms</h2>
        <p>
          We may update these terms. If a change materially reduces your rights we will notify
          account holders by email or in the product before it takes effect, and continuing to use
          the service after that date means you accept the updated terms.
        </p>
      </section>

      <section id="law">
        <h2>11. Governing law</h2>
        <p>
          These terms are governed by the laws of the {COMPANY.governingLaw}, without regard to its
          conflict-of-laws rules. You and we agree to the exclusive jurisdiction of the state and
          federal courts located in Arizona, except that either party may seek injunctive relief in
          any court of competent jurisdiction.
        </p>
      </section>

      <section id="contact">
        <h2>12. Contact</h2>
        <p>
          Questions about these terms: <a href={`mailto:${COMPANY.supportEmail}`}>{COMPANY.supportEmail}</a>.
          Questions about your data: <a href={`mailto:${COMPANY.privacyEmail}`}>{COMPANY.privacyEmail}</a>.
        </p>
      </section>
    </>
  )
}
