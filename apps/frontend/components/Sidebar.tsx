'use client'

import { useEffect, useRef, useState } from 'react'
import { useSession, signOut } from 'next-auth/react'
import Link from 'next/link'
import { Upload, Table, Settings, BrainCircuit, BarChart, SearchCheck, Shield, Activity, Key, Beaker, ListChecks, LogOut, User, Menu, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export default function Sidebar() {
  const { data: session } = useSession()
  const userName = session?.user?.name || 'Guest'
  const userEmail = session?.user?.email || ''
  const userImage = session?.user?.image || ''

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

  const closeDrawer = () => {
    setOpen(false)
    hamburgerRef.current?.focus()
  }

  const menuItems = [
    { name: 'Load Data', icon: <Upload size={20} />, href: '/upload' },
    { name: 'Review Data', icon: <Table size={20} />, href: '/review' },
    { name: 'Explore Data', icon: <SearchCheck size={20} />, href: '/explore' },
    { name: 'Build Model', icon: <BrainCircuit size={20} />, href: '/model' },
    { name: 'Training Jobs', icon: <ListChecks size={20} />, href: '/training' },
    { name: 'Create Predictions', icon: <BarChart size={20} />, href: '/predict' },
    { name: 'A/B Testing', icon: <Beaker size={20} />, href: '/experiments' },
    { name: 'Monitor', icon: <Activity size={20} />, href: '/monitor' },
  ]

  return (
    <>
      {/* Hamburger toggle — outside the translated drawer so it stays reachable
          when the drawer is off-canvas. Hidden at lg+ where the drawer is pinned. */}
      <button
        ref={hamburgerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={open}
        aria-controls="app-sidebar"
        className="fixed top-3 left-3 z-40 rounded-md bg-gray-900 p-2 text-white shadow-lg lg:hidden"
      >
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Backdrop closes the drawer on mobile */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          aria-hidden="true"
          className="fixed inset-0 z-20 bg-black/40 lg:hidden"
        />
      )}

      <aside
        ref={navRef}
        id="app-sidebar"
        aria-label="Sidebar"
        onKeyDown={(e) => {
          if (e.key === 'Escape' && open) closeDrawer()
        }}
        // `invisible` (visibility:hidden) — not just an off-canvas transform —
        // so the closed drawer's links leave the tab order and AT below lg;
        // `lg:visible`/`lg:translate-x-0` keep it always-open on desktop.
        className={`fixed top-0 left-0 h-screen w-64 bg-gray-900 text-white flex flex-col justify-between p-4 z-30 transform transition-transform lg:visible lg:translate-x-0 ${
          open ? 'visible translate-x-0' : 'invisible -translate-x-full'
        }`}
      >
        <div>
          <h1 className="text-xl font-bold mb-6">Modeling App</h1>
          <nav className="space-y-2" aria-label="Main navigation">
            {menuItems.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setOpen(false)}
                className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded"
              >
                {item.icon}
                <span>{item.name}</span>
              </Link>
            ))}
          </nav>
        </div>
        <div className="space-y-2 border-t border-gray-700 pt-4">
          <div className="p-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="w-full justify-start text-left hover:bg-gray-800">
                  <div className="flex items-center space-x-3">
                    {userImage ? (
                      <img
                        src={userImage}
                        alt={userName}
                        className="w-8 h-8 rounded-full"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                        <User size={16} />
                      </div>
                    )}
                    <div className="flex-1 overflow-hidden">
                      <p className="text-sm font-semibold truncate">{userName}</p>
                      <p className="text-xs text-gray-400 truncate">{userEmail}</p>
                    </div>
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/settings" onClick={() => setOpen(false)}>
                    <Settings className="mr-2 h-4 w-4" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => signOut()}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <Link href="/settings/api" onClick={() => setOpen(false)} className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
            <Key size={20} />
            <span>API Keys</span>
          </Link>
          <Link href="/admin" onClick={() => setOpen(false)} className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
            <Shield size={20} />
            <span>Admin</span>
          </Link>
        </div>
      </aside>
    </>
  )
}
