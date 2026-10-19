import Link from 'next/link'
import { COMPANY } from '@/lib/legal/company'
import { NAV_LINKS } from '@/lib/publicLinks'

/** The one header of the public pages: the product name, then `NAV_LINKS` (#772). */
export function PublicNav() {
  const links = NAV_LINKS
  return (
    <nav
      aria-label="Public"
      className="flex w-full flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-border pb-3 text-sm"
    >
      <Link href="/" className="font-semibold text-foreground hover:underline">
        {COMPANY.serviceName}
      </Link>
      <ul className="flex flex-wrap items-center gap-x-5 gap-y-1">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="text-muted-foreground transition-all hover:text-foreground hover:underline">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}
