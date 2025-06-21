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
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  
  // Get the API URL from environment variables
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true)
        
        // Get authentication token
        const token = await getAuthToken()
        
        // Fetch list of available datasets
        const response = await axios.get(`${apiUrl}/api/user_data`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        console.log('Datasets Data:', response.data)
        setDatasets(response.data)
      } catch (err) {
        console.error(err)
        setError('Failed to fetch data')
      } finally {
        setIsLoading(false)
      }
    }

    if (session) {
      fetchData()
    }
  }, [session, apiUrl])

  if (!session) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Please sign in to explore datasets</p>
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
            <Link href="/load">
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
                <p className="text-sm text-gray-500">
                  {dataset.num_rows} rows × {dataset.num_columns} columns
                </p>
                <p className="text-sm text-gray-500 mt-2 mb-4">
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