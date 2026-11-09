'use client'

import { ThemeToggle } from '@/components/ThemeToggle'
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import { useSession, signOut } from 'next-auth/react'
import type { Session } from 'next-auth'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { HugeiconsIcon } from '@hugeicons/react'
import { Activity01Icon, AiBrain01Icon, Cancel01Icon, ChartColumnIcon, CheckListIcon, DashboardSquare01Icon, Key01Icon, Logout01Icon, Menu01Icon, SearchList01Icon, Settings02Icon, Shield01Icon, Table01Icon, Upload04Icon, UserIcon } from '@hugeicons/core-free-icons'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/brand/Logo'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const LINK = 'flex items-center gap-2.5 rounded-md px-2.5 py-2 font-medium text-foreground transition-colors hover:bg-card'
// The page you are on: a white "selected cell" with the petrol edge.
const ACTIVE = 'bg-card font-bold text-primary shadow-[inset_3px_0_0_var(--primary)]'

const isCurrent = (pathname: string | null, href: string) => Boolean(pathname?.startsWith(href))

const MENU_ITEMS = [
  { name: 'Dashboard', icon: <HugeiconsIcon icon={DashboardSquare01Icon} size={18} />, href: '/dashboard' },
  { name: 'Load Data', icon: <HugeiconsIcon icon={Upload04Icon} size={18} />, href: '/upload' },
  { name: 'Review Data', icon: <HugeiconsIcon icon={Table01Icon} size={20} />, href: '/review' },
  { name: 'Explore Data', icon: <HugeiconsIcon icon={SearchList01Icon} size={20} />, href: '/explore' },
  { name: 'Build Model', icon: <HugeiconsIcon icon={AiBrain01Icon} size={20} />, href: '/model' },
  { name: 'Training Jobs', icon: <HugeiconsIcon icon={CheckListIcon} size={20} />, href: '/training' },
  { name: 'Create Predictions', icon: <HugeiconsIcon icon={ChartColumnIcon} size={20} />, href: '/predict' },
  { name: 'Monitor', icon: <HugeiconsIcon icon={Activity01Icon} size={20} />, href: '/monitor' },
]

type MenuItem = (typeof MENU_ITEMS)[number]
type Account = { name?: string | null; email?: string | null; image?: string | null }
type ToggleProps = { open: boolean; onToggle: VoidFunction; buttonRef: RefObject<HTMLButtonElement | null> }
type AvatarProps = { image: Account['image']; name: string }
type AccountMenuProps = { account?: Account; onNavigate: VoidFunction }
type FooterProps = { session: Session | null; onNavigate: VoidFunction }

function leave() {
  void signOut()
}

/** Outside the translated drawer so it stays reachable when the drawer is
 *  off-canvas. Hidden at lg+ where the drawer is pinned. */
function DrawerToggle(props: ToggleProps) {
  const { open, onToggle, buttonRef } = props
  const label = open ? 'Close navigation menu' : 'Open navigation menu'
  const icon = open ? Cancel01Icon : Menu01Icon
  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-expanded={open}
      aria-controls="app-sidebar"
      className="fixed top-3 left-3 z-50 rounded-md border border-border bg-card p-2 text-foreground shadow-sm lg:hidden"
    >
      <HugeiconsIcon icon={icon} size={20} />
    </button>
  )
}

function Avatar(props: AvatarProps) {
  const { image, name } = props
  if (image) return <img src={image} alt={name} className="w-8 h-8 rounded-full" />
  return (
    <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
      <HugeiconsIcon icon={UserIcon} size={16} />
    </div>
  )
}

function AccountMenu(props: AccountMenuProps) {
  const { account = {}, onNavigate } = props
  const name = account.name || 'Guest'
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-auto w-full min-w-0 justify-start overflow-hidden px-2 py-1.5 text-left hover:bg-card">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <Avatar image={account.image} name={name} />
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-semibold truncate">{name}</p>
              <p className="text-xs text-muted-foreground truncate">{account.email}</p>
            </div>
          </div>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end">
        <DropdownMenuLabel>My Account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings" onClick={onNavigate}>
            <HugeiconsIcon icon={Settings02Icon} className="mr-2 h-4 w-4" />
            Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={leave}>
          <HugeiconsIcon icon={Logout01Icon} className="mr-2 h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function SidebarFooter(props: FooterProps) {
  const { session, onNavigate } = props
  return (
    <div className="space-y-1 border-t border-border pt-4">
      <div className="p-2">
        <AccountMenu account={session?.user} onNavigate={onNavigate} />
      </div>
      <Link href="/settings/api" onClick={onNavigate} className={LINK}>
        <HugeiconsIcon icon={Key01Icon} size={18} />
        <span>API Keys</span>
      </Link>
      {/* Admins only (#477): the flag is computed server-side in auth.ts;
          middleware.ts guards the route itself, this just hides the door. */}
      {session?.isAdmin && (
        <Link href="/admin" onClick={onNavigate} className={LINK}>
          <HugeiconsIcon icon={Shield01Icon} size={18} />
          <span>Admin</span>
        </Link>
      )}
      {/* The only way to reach dark mode. Before #407 the `.dark` class was
          never set by anything, so all 27 `dark:` utilities were dead. */}
      <div className="px-2 pt-2">
        <ThemeToggle />
      </div>
    </div>
  )
}

export default function Sidebar() {
  const { data: session } = useSession()
  const pathname = usePathname()

  // Below `lg` the sidebar is an off-canvas drawer toggled by a hamburger; at
  // `lg`+ it's always pinned (issue #282).
  const [open, setOpen] = useState(false)
  const hamburgerRef = useRef<HTMLButtonElement>(null)
  const navRef = useRef<HTMLElement>(null)

  // On open, move focus into the drawer; Escape closes and returns focus to the
  // hamburger — mirroring the FeedbackWidget dialog's keyboard pattern.
  useEffect(() => {
    if (open) navRef.current?.querySelector<HTMLElement>('a')?.focus()
  }, [open])

  const close = () => setOpen(false)
  const toggle = () => setOpen(!open)
  const closeOnEscape = (e: KeyboardEvent) => {
    if (e.key !== 'Escape' || !open) return
    setOpen(false)
    hamburgerRef.current?.focus()
  }
  const navLink = (item: MenuItem) => (
    <Link
      key={item.name}
      href={item.href}
      onClick={close}
      aria-current={isCurrent(pathname, item.href) ? 'page' : undefined}
      className={isCurrent(pathname, item.href) ? `${LINK} ${ACTIVE}` : LINK}
    >
      {item.icon}
      <span>{item.name}</span>
    </Link>
  )

  return (
    <>
      <DrawerToggle open={open} onToggle={toggle} buttonRef={hamburgerRef} />

      {/* Backdrop closes the drawer on mobile */}
      {open && <div onClick={close} aria-hidden="true" className="fixed inset-0 z-20 bg-foreground/30 lg:hidden" />}

      <aside
        ref={navRef}
        id="app-sidebar"
        aria-label="Sidebar"
        onKeyDown={closeOnEscape}
        // `invisible` (visibility:hidden) — not just an off-canvas transform —
        // so the closed drawer's links leave the tab order and AT below lg;
        // `lg:visible`/`lg:translate-x-0` keep it always-open on desktop.
        style={{ ['--logo-surface' as string]: 'var(--muted)' }}
        className={`fixed top-0 left-0 h-dvh w-64 overflow-y-auto border-r border-border bg-muted text-foreground flex flex-col justify-between p-4 z-30 transform transition-transform lg:visible lg:translate-x-0 ${
          open ? 'visible translate-x-0' : 'invisible -translate-x-full'
        }`}
      >
        <div>
          <Link href="/dashboard" onClick={close} className="mb-6 block px-1 text-xl">
            <Logo />
          </Link>
          <nav className="space-y-0.5" aria-label="Main navigation">
            {MENU_ITEMS.map(navLink)}
          </nav>
        </div>
        <SidebarFooter session={session} onNavigate={close} />
      </aside>
    </>
  )
}
