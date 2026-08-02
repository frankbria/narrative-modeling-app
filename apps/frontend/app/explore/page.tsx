'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'

// Define the Dataset type
interface Dataset {
  _id: string;  // MongoDB uses _id instead of id
  filename: string;
  num_rows: number;
  num_columns: number;
  created_at: string;
  user_id: string;
}

export default function ExploreDataPage() {
  const { data: session } = useSession()
  // `useSession().data` is a new object every render; keying a hook on it re-runs
  // that hook forever (#402). Depend on the id, which is a string.
  const userId = session?.user?.id
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  
  // Get the API URL from environment variables
  // NEXT_PUBLIC_API_URL carries the /api/v1 prefix (CLAUDE.md, Environment
  // Variables). This defaulted to a bare origin and then re-added /api, so the
  // request went to /api/v1/api/user_data and 404'd — the same bug as #406,
  // missed there because that sweep only looked at `fetch(` templates and this
  // call uses axios.
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true)
        
        // Get authentication token
        const token = await getAuthToken()
        
        // Fetch list of available datasets
        const response = await axios.get(`${apiUrl}/user_data`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        setDatasets(response.data)
      } catch (err) {
        console.error(err)
        setError('Failed to fetch data')
      } finally {
        setIsLoading(false)
      }
    }

    if (userId) {
      fetchData()
    }
  }, [userId, apiUrl])

  if (!session) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Please sign in to explore datasets</p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin mr-2 text-blue-600" />
        <span>Loading data...</span>
      </div>
    )
  }

  if (error) {
    return <div className="text-red-500 p-6">{error}</div>
  }

  return (
    <div className="flex-1 p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Explore Datasets</h1>
      </div>
      
      {datasets.length === 0 ? (
        <div className="border rounded-lg shadow-sm p-6">
          <p className="text-center mb-4">No datasets available. Please upload a dataset first.</p>
          <div className="flex justify-center">
            <Link href="/upload">
              <Button>Upload Dataset</Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {datasets.map((dataset, index) => (
            <div key={`dataset-${dataset._id || index}`} className="border rounded-lg shadow-sm hover:shadow-md transition-shadow">
              <div className="p-6">
                <h3 className="text-lg font-semibold">{dataset.filename}</h3>
                <p className="text-sm text-muted-foreground">
                  {dataset.num_rows} rows × {dataset.num_columns} columns
                </p>
                <p className="text-sm text-muted-foreground mt-2 mb-4">
                  Created: {new Date(dataset.created_at).toLocaleDateString()}
                </p>
                <Link href={`/explore/${dataset._id}`}>
                  <Button className="w-full">View Analysis</Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}