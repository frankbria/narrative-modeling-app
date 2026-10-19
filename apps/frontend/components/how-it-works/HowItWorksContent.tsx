import Link from 'next/link'
import { PublicNav } from '@/components/PublicNav'
import { StageList } from './StageList'
import { Walkthrough } from './Walkthrough'

export function HowItWorksContent() {
  return (
    <div className="mx-auto w-full max-w-5xl px-6 pb-24 pt-6 text-foreground">
      <PublicNav />
      <article className="prose prose-slate mt-8 max-w-none dark:prose-invert prose-headings:scroll-mt-6">
        <h1>How it works</h1>
        <p className="lead">
          Eight guided stages take a spreadsheet to a trained, explained model. Every screenshot
          below is the real app, signed in as a demo account.
        </p>
        <Walkthrough />
        <section aria-labelledby="stages-heading" id="stages">
          <h2 id="stages-heading">The eight stages</h2>
          <StageList />
        </section>
        <p>
          Prices are on the <Link href="/pricing">pricing page</Link>; what happens to your data is
          on the <Link href="/security">security page</Link>.
        </p>
      </article>
    </div>
  )
}
