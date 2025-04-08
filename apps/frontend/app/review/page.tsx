// apps/frontend/app/review/page.tsx
import { useUser } from '@clerk/nextjs'

export default function ModelPage() {
  const { isSignedIn } = useUser()

  if (!isSignedIn) return <p>Please log in to access this page.</p>
  
  return <h1 className="text-2xl font-bold text-gray-800">Review Data</h1>
}
