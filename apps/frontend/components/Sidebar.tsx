'use client'

import { useSession, signOut } from 'next-auth/react'
import Link from 'next/link'
import { Upload, Table, Settings, BrainCircuit, BarChart, SearchCheck, Shield, Activity, Key, Beaker, LogOut, User } from 'lucide-react'
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

  const menuItems = [
    { name: 'Load Data', icon: <Upload size={20} />, href: '/load' },
    { name: 'Review Data', icon: <Table size={20} />, href: '/review' },
    { name: 'Explore Data', icon: <SearchCheck size={20} />, href: '/explore' },
    { name: 'Build Model', icon: <BrainCircuit size={20} />, href: '/model' },
    { name: 'Create Predictions', icon: <BarChart size={20} />, href: '/predict' },
    { name: 'A/B Testing', icon: <Beaker size={20} />, href: '/experiments' },
    { name: 'Monitor', icon: <Activity size={20} />, href: '/monitor' },
  ]

  return (
    <div className="fixed top-0 left-0 h-screen w-64 bg-gray-900 text-white flex flex-col justify-between p-4 z-10">
      <div>
        <h1 className="text-xl font-bold mb-6">Modeling App</h1>
        <nav className="space-y-2">
          {menuItems.map((item) => (
            <Link
              key={item.name}
              href={item.href}
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
                <Link href="/settings">
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
        <Link href="/settings/api" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
          <Key size={20} />
          <span>API Keys</span>
        </Link>
        <Link href="/admin" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
          <Shield size={20} />
          <span>Admin</span>
        </Link>
      </div>
    </div>
  )
}
