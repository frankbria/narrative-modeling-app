'use client'

import Link from 'next/link'
import { useInAppShell } from '@/components/AppShell'
import { Logo } from '@/components/brand/Logo'
import { Button } from '@/components/ui/button'
import { NAV_LINKS } from '@/lib/publicLinks'

/** The one header of the public pages: the logo, `NAV_LINKS` (#772), then the way in. */
function PublicNavBar() {
  return (
    <nav
      aria-label="Public"
      className="flex w-full flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border pb-4 text-sm"
    >
      <Link href="/" className="text-lg">
        <Logo />
      </Link>
      <ul className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {NAV_LINKS.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="font-medium text-muted-foreground transition-all hover:text-foreground">
              {link.label}
            </Link>
          </li>
        ))}
        <li>
          <Link href="/auth/signin" className="font-semibold text-foreground transition-all hover:text-primary">
            Sign in
          </Link>
        </li>
        <li>
          <Button asChild size="sm">
            <Link href="/auth/signin">Start free</Link>
          </Button>
        </li>
      </ul>
    </nav>
  )
}

/** Inside the app shell a signed-in visitor already has the app's navigation, so this steps aside (#1190). */
export function PublicNav() {
  const view = { true: null, false: <PublicNavBar /> }
  return view[`${useInAppShell()}`]
}
