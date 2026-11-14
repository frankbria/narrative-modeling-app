/**
 * The root layout mounts the public-page counter for signed-out visitors only (#1211).
 * PublicPageviews' own session check is the second line; this test holds the first,
 * so removing the mount or moving it where a signed-in page renders fails CI.
 *
 * The element walk sees what the layout writes, not what its children render, so the
 * last test keeps every other module from naming the counter at all.
 */
import { readdirSync, readFileSync } from 'fs'
import { join } from 'path'
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
    // Assigning undefined to process.env stores the string "undefined".
    if (originalDomain === undefined) delete process.env.PLAUSIBLE_DOMAIN
    else process.env.PLAUSIBLE_DOMAIN = originalDomain
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

  it('is named by the root layout alone, so no component can render the counter elsewhere', () => {
    const root = join(__dirname, '..', '..')
    const notSource = new Set(['node_modules', '.next', '__tests__', 'e2e'])
    const sources = readdirSync(root, { withFileTypes: true })
      .filter((entry) => !notSource.has(entry.name))
      .flatMap((entry) =>
        entry.isDirectory()
          ? readdirSync(join(root, entry.name), { recursive: true, encoding: 'utf8' }).map((file) => join(entry.name, file))
          : [entry.name],
      )
      .filter((file) => /\.tsx?$/.test(file))
    // Any mention, whatever the import form or quote style: only the layout may name it.
    const namers = sources
      .filter((file) => file !== 'components/analytics/PublicPageviews.tsx')
      .filter((file) => /\bPublicPageviews\b/.test(readFileSync(join(root, file), 'utf8')))
    expect(namers).toEqual(['app/layout.tsx'])
  })
})
