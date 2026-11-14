/**
 * The root layout mounts the public-page counter for signed-out visitors only (#1211).
 * PublicPageviews' own session check is the second line; this test holds the first,
 * so removing the mount or moving it where a signed-in page renders fails CI.
 */
import { isValidElement, type ReactElement, type ReactNode } from 'react'
import type { Session } from 'next-auth'
import RootLayout from '@/app/layout'
import { PublicPageviews } from '@/components/analytics/PublicPageviews'

let session: Session | null = null

jest.mock('@/auth', () => ({ auth: async () => session }))
jest.mock('next/font/google', () => ({ Schibsted_Grotesk: () => ({ variable: 'font-schibsted' }) }))

function elementsOfType(node: ReactNode, type: ReactElement['type']): ReactElement<{ domain: string }>[] {
  if (Array.isArray(node)) return node.flatMap((child) => elementsOfType(child, type))
  if (!isValidElement<{ children?: ReactNode; domain: string }>(node)) return []
  const below = elementsOfType(node.props.children, type)
  return node.type === type ? [node, ...below] : below
}

async function countersMounted(): Promise<ReactElement<{ domain: string }>[]> {
  return elementsOfType(await RootLayout({ children: <p>page</p> }), PublicPageviews)
}

describe('RootLayout and the public-page counter', () => {
  const originalDomain = process.env.PLAUSIBLE_DOMAIN

  afterEach(() => {
    session = null
    process.env.PLAUSIBLE_DOMAIN = originalDomain
  })

  it('mounts the counter once for a signed-out visitor, under the configured Plausible site', async () => {
    process.env.PLAUSIBLE_DOMAIN = 'sheetpredict.app'
    const counters = await countersMounted()
    expect(counters).toHaveLength(1)
    expect(counters[0].props.domain).toBe('sheetpredict.app')
  })

  it('does not mount the counter for a signed-in visitor', async () => {
    session = { user: { id: 'user-1', email: 'ana@example.com' }, expires: '2099-01-01T00:00:00.000Z' }
    expect(await countersMounted()).toHaveLength(0)
  })
})
