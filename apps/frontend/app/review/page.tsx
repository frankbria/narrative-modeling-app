'use client'

// apps/frontend/app/review/page.tsx
import { useUser, useSession } from '@clerk/nextjs'
import { useState, useEffect, useCallback } from 'react'
import { StatsCard } from '@/components/StatsCard'
import { calculateDescriptiveStats, StatItem } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDatasetChatContext } from '@/lib/hooks/useDatasetChatContext';
import ReactMarkdown from 'react-markdown';

interface UserData {
  id: string
  filename: string
  s3_url: string
  num_rows: number
  num_columns: number
  data_schema: Array<{
    field_name: string
    field_type: string
    data_type: string
    inferred_dtype: string
    unique_values: number
    missing_values: number
    example_values: string[]
    is_constant: boolean
    is_high_cardinality: boolean
  }>
  created_at: string
  updated_at: string
  headers: string[]
  previewData: Array<Array<string | number | boolean | null>>
  error?: string
}

export default function ReviewPage() {
  const { isSignedIn, user } = useUser()
  const { session } = useSession()
  const [data, setData] = useState<UserData | null>(null)
  const [stats, setStats] = useState<StatItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { rawMarkdown, isLoading: isLoadingAISummary, error: aiSummaryError, isAvailable: isAISummaryAvailable } = useDatasetChatContext(data?.id || null);

  const fetchPreviewData = useCallback(async () => {
    if (!user?.id) return

    try {
      setIsLoading(true)
      setError(null)
      
      // Ensure the URL has a protocol
      let backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
        backendUrl = `http://${backendUrl}`
      }
      
      // Remove trailing /api if present
      backendUrl = backendUrl.replace(/\/api$/, '')
      
      console.log('Fetching preview data from:', `${backendUrl}/api/user_data/preview/${user.id}`)
      
      const response = await fetch(`${backendUrl}/api/user_data/preview/${user.id}`, {
        headers: {
          'Authorization': `Bearer ${await session?.getToken()}`
        }
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to fetch preview data: ${errorText}`)
      }

      const result = await response.json()
      setData(result)
      
      // Calculate descriptive statistics
      if (result.headers && result.previewData) {
        const calculatedStats = calculateDescriptiveStats(result.previewData, result.headers)
        setStats(calculatedStats)
      }
    } catch (err) {
      console.error('Error fetching preview data:', err)
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }, [user?.id, session])

  useEffect(() => {
    if (isSignedIn) {
      fetchPreviewData()
    }
  }, [isSignedIn, fetchPreviewData])

  if (!isSignedIn) return <p>Please log in to access this page.</p>
  
  return (
    <div className="p-6 ml-64 mr-80">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Review Data</h1>
      
      {isLoading && <p>Loading...</p>}
      
      {error && (
        <div className="p-4 mb-6 bg-red-50 border border-red-200 rounded-md text-red-700">
          <p className="font-medium">Error:</p>
          <p>{error}</p>
        </div>
      )}
      
      {!isLoading && !data && (
        <div className="p-4 mb-6 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-700">
          <p>No data available. Please upload a file in the Load Data page.</p>
        </div>
      )}
      
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          <div className="md:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle>Your Datasets</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div
                    className={`p-3 rounded-md cursor-pointer ${
                      data.id === data.id
                        ? 'bg-blue-100 border border-blue-300'
                        : 'hover:bg-gray-100'
                    }`}
                    onClick={() => fetchPreviewData()}
                  >
                    <p className="font-medium truncate">{data.filename}</p>
                    <p className="text-sm text-gray-500">
                      {data.num_rows ? `${data.num_rows} rows` : 'Unknown rows'} × {data.num_columns ? `${data.num_columns} columns` : 'Unknown columns'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          
          <div className="md:col-span-3">
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Dataset Information</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="mt-6">
                      {isLoadingAISummary ? (
                        <div className="text-sm text-gray-500">
                          <p>Loading AI analysis...</p>
                        </div>
                      ) : aiSummaryError ? (
                        <div className="text-sm text-red-500">
                          <p>Error loading AI analysis: {aiSummaryError}</p>
                        </div>
                      ) : !isAISummaryAvailable ? (
                        <div className="text-sm text-gray-500">
                          <p>AI analysis is not yet available. It will be generated automatically after the dataset is processed.</p>
                        </div>
                      ) : rawMarkdown ? (
                        <div className="prose prose-sm max-w-none">
                          <div className="space-y-6">
                            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                              <h4 className="text-blue-800 font-medium mb-2">Overview</h4>
                              <div className="text-blue-700">
                                <ReactMarkdown>
                                  {rawMarkdown.split('Potential Data Issues')[0] || 'No overview available.'}
                                </ReactMarkdown>
                              </div>
                            </div>
                            
                            <div className="bg-red-50 p-4 rounded-lg border border-red-200">
                              <h4 className="text-red-800 font-medium mb-2">Data Quality Issues</h4>
                              <div className="text-red-700">
                                <ReactMarkdown>
                                  {rawMarkdown.includes('Potential Data Issues')
                                    ? rawMarkdown.split('Potential Data Issues')[1]?.split('Suggested Relationships')[0] || 'No data quality issues identified.'
                                    : 'No data quality issues identified.'}
                                </ReactMarkdown>
                              </div>
                            </div>
                            
                            <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                              <h4 className="text-green-800 font-medium mb-2">Potential Relationships</h4>
                              <div className="text-green-700">
                                <ReactMarkdown>
                                  {rawMarkdown.includes('Suggested Relationships')
                                    ? rawMarkdown.split('Suggested Relationships')[1]?.split('Recommendations for Further Analysis')[0] || 'No potential relationships identified.'
                                    : 'No potential relationships identified.'}
                                </ReactMarkdown>
                              </div>
                            </div>
                            
                            <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
                              <h4 className="text-purple-800 font-medium mb-2">Recommendations</h4>
                              <div className="text-purple-700">
                                <ReactMarkdown>
                                  {rawMarkdown.includes('Recommendations for Further Analysis')
                                    ? rawMarkdown.split('Recommendations for Further Analysis')[1] || 'No recommendations available.'
                                    : 'No recommendations available.'}
                                </ReactMarkdown>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 text-sm text-gray-500">
                              <div>
                                <p>Created</p>
                                <p className="font-medium text-gray-700">
                                  {data.created_at ? new Date(data.created_at).toLocaleString() : 'Unknown'}
                                </p>
                              </div>
                              <div>
                                <p>Last Updated</p>
                                <p className="font-medium text-gray-700">
                                  {data.updated_at ? new Date(data.updated_at).toLocaleString() : 'Unknown'}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="text-sm text-gray-500">
                          <p>No AI analysis available.</p>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}
      
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-4">
            {stats.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {stats.map((stat, index) => (
                  <StatsCard key={index} stats={stat} />
                ))}
              </div>
            )}
            
            {data.headers && data.previewData && data.previewData.length > 0 ? (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Data Preview</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gray-800">
                          {data.headers.map((header: string, index: number) => (
                            <TableHead key={index} className="text-white font-semibold">
                              {header}
                            </TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.previewData.map((row: Array<string | number | boolean | null>, rowIndex: number) => (
                          <TableRow
                            key={rowIndex}
                            className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                          >
                            {row.map((cell: string | number | boolean | null, cellIndex: number) => (
                              <TableCell key={cellIndex} className="text-gray-900">
                                {cell?.toString() ?? ''}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Data Preview</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-700">
                    <p className="font-medium">No preview data available</p>
                    <p className="text-sm mt-1">
                      {data.error ? data.error : "The preview data could not be loaded. This might be due to an issue with the S3 storage or file format."}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
