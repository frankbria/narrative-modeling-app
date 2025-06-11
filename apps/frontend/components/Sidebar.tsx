'use client'

import { useUser, UserButton } from '@clerk/nextjs'
import Link from 'next/link'
import { Upload, Table, Settings, BrainCircuit, BarChart, SearchCheck, Shield } from 'lucide-react'

export default function Sidebar() {
  const { user } = useUser()
  const userName = user?.fullName || 'Guest'

  const menuItems = [
    { name: 'Load Data', icon: <Upload size={20} />, href: '/load' },
    { name: 'Review Data', icon: <Table size={20} />, href: '/review' },
    { name: 'Explore Data', icon: <SearchCheck size={20} />, href: '/explore' },
    { name: 'Build Model', icon: <BrainCircuit size={20} />, href: '/model' },
    { name: 'Create Predictions', icon: <BarChart size={20} />, href: '/predict' },
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
          <p className="text-sm text-gray-400 mb-1">Signed in </p>
          <p className="text-sm font-semibold truncate">{userName}</p>
        </div>
        <div className="flex items-center space-x-2 p-2">
          <UserButton />
        </div>
        <Link href="/admin" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
          <Shield size={20} />
          <span>Admin</span>
        </Link>
        <Link href="/settings" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
          <Settings size={20} />
          <span>Settings</span>
        </Link>
      </div>
    </div>
  )
}
