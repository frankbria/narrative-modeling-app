import { PublicNav } from '@/components/PublicNav'
import { DatasetSection } from './DatasetSection'
import { RetentionSection } from './RetentionSection'
import { ApiSection, RefundSection } from './RefundAndApiSection'
import { SubProcessorSection } from './SubProcessorSection'

export function SecurityContent() {
  return (
    <div className="mx-auto w-full max-w-3xl px-6 pb-24 pt-6 text-foreground">
      <PublicNav />
      <article className="prose prose-slate mt-8 max-w-none dark:prose-invert prose-headings:scroll-mt-6">
        <h1>Security and your data</h1>
        <p className="lead">
          What happens to a dataset after you upload it, who else receives any of it, and how it
          is removed. This page describes what the code does today.
        </p>
        <DatasetSection />
        <SubProcessorSection />
        <RetentionSection />
        <RefundSection />
        <ApiSection />
      </article>
    </div>
  )
}
