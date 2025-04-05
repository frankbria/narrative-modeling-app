'use client'
import { useUser } from '@clerk/nextjs'

export default function LoadPage() {
  const { isSignedIn } = useUser()

  if (!isSignedIn) return <p>Please log in to access this page.</p>

  return (
    <div>
      <h1 className="text-2xl font-bold">Load Data</h1>
      {/* File upload UI goes here */}
    </div>
  )
}
