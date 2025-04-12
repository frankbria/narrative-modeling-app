'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Loader2, BarChart2, PieChart, LineChart, ScatterChart } from 'lucide-react'
import { AIChat } from '@/components/AIChat'

interface Dataset {
  id: string
  name: string
  description: string
  created_at: string
  row_count: number
  column_count: number
}

export default function ExplorePage() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchDatasets = async () => {
      try {
        setIsLoading(true)
        // In a real implementation, this would fetch from your API
        // For now, we'll simulate a delay and return mock data
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        // Mock data
        const mockDatasets: Dataset[] = [
          {
            id: '1',
            name: 'Customer Data',
            description: 'Customer purchase history and demographics',
            created_at: '2023-05-15T10:30:00Z',
            row_count: 12500,
            column_count: 18
          },
          {
            id: '2',
            name: 'Sales Transactions',
            description: 'Daily sales transactions by product',
            created_at: '2023-06-22T14:45:00Z',
            row_count: 8750,
            column_count: 12
          },
          {
            id: '3',
            name: 'Website Analytics',
            description: 'User behavior and page views',
            created_at: '2023-07-10T09:15:00Z',
            row_count: 25000,
            column_count: 15
          }
        ]
        
        setDatasets(mockDatasets)
        setError(null)
      } catch (err) {
        console.error('Error fetching datasets:', err)
        setError('Failed to load datasets. Please try again later.')
      } finally {
        setIsLoading(false)
      }
    }

    fetchDatasets()
  }, [])

  return (
    <div className="flex h-screen">
      {/* Left Menu - Fixed */}
      <div className="fixed left-0 top-0 h-screen w-64 bg-gray-900 text-white p-4">
        <h1 className="text-xl font-bold mb-6">Modeling App</h1>
        <nav className="space-y-2">
          <a href="/load" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
            <span>Load Data</span>
          </a>
          <a href="/review" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
            <span>Review Data</span>
          </a>
          <a href="/explore" className="flex items-center space-x-2 bg-gray-800 p-2 rounded">
            <span>Explore Data</span>
          </a>
          <a href="/model" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
            <span>Build Model</span>
          </a>
          <a href="/predict" className="flex items-center space-x-2 hover:bg-gray-800 p-2 rounded">
            <span>Create Predictions</span>
          </a>
        </nav>
      </div>

      {/* Main Content - Centered */}
      <div className="flex-1 ml-64 mr-80 p-6">
        <h1 className="text-2xl font-bold mb-6">Explore Data</h1>
        
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500 mr-2" />
            <span>Loading datasets...</span>
          </div>
        ) : error ? (
          <Card className="bg-red-50 border-red-200">
            <CardContent className="p-6">
              <p className="text-red-600">{error}</p>
              <Button 
                variant="outline" 
                className="mt-4"
                onClick={() => window.location.reload()}
              >
                Try Again
              </Button>
            </CardContent>
          </Card>
        ) : datasets.length === 0 ? (
          <Card>
            <CardContent className="p-6">
              <p className="text-gray-600">No datasets available. Upload a dataset to get started.</p>
              <Button 
                className="mt-4"
                onClick={() => window.location.href = '/load'}
              >
                Upload Dataset
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {datasets.map(dataset => (
                <Card key={dataset.id} className="hover:shadow-md transition-shadow">
                  <CardHeader>
                    <CardTitle>{dataset.name}</CardTitle>
                    <CardDescription>{dataset.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex justify-between text-sm text-gray-500 mb-4">
                      <span>{dataset.row_count.toLocaleString()} rows</span>
                      <span>{dataset.column_count} columns</span>
                    </div>
                    <div className="flex space-x-2">
                      <Button variant="outline" size="sm" className="flex-1">
                        <BarChart2 className="h-4 w-4 mr-1" />
                        Bar Chart
                      </Button>
                      <Button variant="outline" size="sm" className="flex-1">
                        <PieChart className="h-4 w-4 mr-1" />
                        Pie Chart
                      </Button>
                      <Button variant="outline" size="sm" className="flex-1">
                        <LineChart className="h-4 w-4 mr-1" />
                        Line Chart
                      </Button>
                      <Button variant="outline" size="sm" className="flex-1">
                        <ScatterChart className="h-4 w-4 mr-1" />
                        Scatter
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            
            <Card>
              <CardHeader>
                <CardTitle>Recent Datasets</CardTitle>
                <CardDescription>Your recently uploaded and accessed datasets</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Rows</TableHead>
                      <TableHead>Columns</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {datasets.map(dataset => (
                      <TableRow key={dataset.id}>
                        <TableCell className="font-medium">{dataset.name}</TableCell>
                        <TableCell>{dataset.description}</TableCell>
                        <TableCell>{new Date(dataset.created_at).toLocaleDateString()}</TableCell>
                        <TableCell>{dataset.row_count.toLocaleString()}</TableCell>
                        <TableCell>{dataset.column_count}</TableCell>
                        <TableCell>
                          <Button variant="outline" size="sm">View</Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Right Side - AIChat */}
      <div className="fixed right-0 top-0 h-screen w-80">
        <AIChat />
      </div>
    </div>
  )
}
