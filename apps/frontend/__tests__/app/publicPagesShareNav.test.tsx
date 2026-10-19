/**
 * One public nav on every public page (#772 AC5): the landing page, pricing, the
 * legal pages, security and how-it-works each render the shared `PublicNav`, so a
 * link added to `lib/publicLinks.ts` appears on all of them.
 */
import { render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom'

jest.mock('@/auth', () => ({ auth: jest.fn().mockResolvedValue(null) }))
jest.mock('next/navigation', () => ({ redirect: jest.fn() }))

import HomePage from '@/app/page'
import PricingPage from '@/app/pricing/page'
import SecurityPage from '@/app/security/page'
import HowItWorksPage from '@/app/how-it-works/page'
import LegalLayout from '@/app/legal/layout'
import { NAV_LINKS } from '@/lib/publicLinks'

const PAGES: [string, () => Promise<React.ReactElement> | React.ReactElement][] = [
  ['landing', () => HomePage()],
  ['pricing', () => <PricingPage />],
  ['security', () => <SecurityPage />],
  ['how it works', () => <HowItWorksPage />],
  ['legal', () => <LegalLayout>text</LegalLayout>],
]

describe.each(PAGES)('%s page', (_name, page) => {
  it('carries the shared public nav, with every link from the shared list', async () => {
    render(await page())
    const nav = screen.getByRole('navigation', { name: /public/i })
    for (const { href, label } of NAV_LINKS) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('href', href)
    }
  })
})
