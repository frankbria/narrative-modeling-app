'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table'
import { Loader2 } from 'lucide-react'
import axios from 'axios'
import { useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'

// Define the EDA summary type
interface EDASummary {
  [key: string]: unknown;
  overview: {
    filename: string;
    shape: number[];
    columns: string[];
    dtypes: Record<string, string>;
  };
  dataQuality: {
    missingData: Record<string, number>;
    missingPercentage: Record<string, number>;
    outliers: Record<string, number>;
    skewness: Record<string, number>;
    lowVarianceFeatures: string[];
  };
  variableInsights: {
    highCardinality: Record<string, number>;
    correlatedFeatures: Record<string, number>;
  };
  transformations: {
    normalize: string[];
    encode: string[];
    drop: string[];
  };
  groupedInsights: Record<string, Record<string, number>>;
}

export default function DatasetAnalysisPage() {
  const params = useParams()
  const { getToken } = useAuth()
  const [summary, setSummary] = useState<EDASummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Get the API URL from environment variables
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true)
        
        // Get authentication token
        const token = await getToken()
        
        // Get dataset ID from params
        const datasetId = params?.id as string
        
        if (!datasetId) {
          setError('No dataset ID provided')
          return
        }

        // First, verify the dataset exists
        const datasetResponse = await axios.get(`${apiUrl}/api/user_data/${datasetId}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })

        if (!datasetResponse.data) {
          setError('Dataset not found')
          return
        }

        // Fetch specific dataset EDA summary
        const response = await axios.get(`${apiUrl}/api/user_data/${datasetId}/eda-summary`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        })

        if (response.data && response.data.summary) {
          setSummary(response.data.summary)
        } else if (response.data) {
          setSummary(response.data)
        } else {
          setError('No summary data available')
        }
      } catch (err) {
        console.error('Error fetching data:', err)
        if (axios.isAxiosError(err)) {
          if (err.response?.status === 422) {
            setError('Invalid dataset ID or format')
          } else if (err.response?.status === 404) {
            setError('Dataset not found')
          } else {
            setError(`Failed to fetch data: ${err.response?.data?.detail || err.message}`)
          }
        } else {
          setError('Failed to fetch data')
        }
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [params?.id, getToken, apiUrl])

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

  if (!summary) {
    return <div className="text-red-500 p-6">No summary data available for this dataset</div>
  }

  // Helper function to safely access nested properties
  const safeGet = <T,>(obj: EDASummary, path: string, defaultValue: T): T => {
    try {
      const result = path.split('.').reduce<Record<string, unknown>>((o, i) => {
        return (o?.[i] as Record<string, unknown>) ?? defaultValue as unknown as Record<string, unknown>;
      }, obj as unknown as Record<string, unknown>);
      return result as T;
    } catch {
      return defaultValue;
    }
  }

  const renderTable = (data: Record<string, number | string | object>) => {
    if (!data || typeof data !== 'object' || Object.keys(data).length === 0) {
      return <div className="text-gray-500">No relevant columns</div>;
    }
    
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className='font-bold'>Column</TableHead>
            <TableHead className='font-bold'>Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(data).map(([key, value]) => (
            <TableRow key={key} className={typeof value === 'number' && value > 30 ? 'bg-red-100' : ''}>
              <TableCell>{key}</TableCell>
              <TableCell>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <div className="flex-1 p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Dataset Analysis</h1>
        <Link href="/explore">
          <Button variant="outline">Back to Datasets</Button>
        </Link>
      </div>
      
      <Card>
        <CardHeader>
          <CardTitle>Dataset Overview</CardTitle>
          <CardDescription>Basic properties of the uploaded dataset</CardDescription>
        </CardHeader>
        <CardContent>
          <p><strong>Filename:</strong> {safeGet<string>(summary, 'overview.filename', 'N/A')}</p>
          <p><strong>Shape:</strong> {Array.isArray(safeGet<number[]>(summary, 'overview.shape', [])) 
            ? safeGet<number[]>(summary, 'overview.shape', []).join(' x ') 
            : 'N/A'}</p>
          <p><strong>Columns:</strong> {Array.isArray(safeGet<string[]>(summary, 'overview.columns', [])) 
            ? safeGet<string[]>(summary, 'overview.columns', []).join(', ') 
            : 'N/A'}</p>
        </CardContent>
      </Card>

      <Accordion type="multiple" className="w-full">
        <AccordionItem value="data-quality" className="border rounded-lg mb-4 overflow-hidden">
          <AccordionTrigger className="bg-blue-50 hover:bg-blue-100 px-4 py-3 font-bold text-blue-800">
            Data Quality
          </AccordionTrigger>
          <AccordionContent className="px-4 py-3">
            <h3 className="text-md font-semibold mb-2">Missing Data (%)</h3>
            {renderTable(safeGet<Record<string, number>>(summary, 'dataQuality.missingPercentage', {}))}

            <h3 className="text-md font-semibold mt-4 mb-2">Outliers</h3>
            {renderTable(safeGet<Record<string, number>>(summary, 'dataQuality.outliers', {}))}

            <h3 className="text-md font-semibold mt-4 mb-2">Skewness</h3>
            {renderTable(safeGet<Record<string, number>>(summary, 'dataQuality.skewness', {}))}

            <h3 className="text-md font-semibold mt-4 mb-2">Low Variance Features</h3>
            <ul className="list-disc list-inside">
              {Array.isArray(safeGet<string[]>(summary, 'dataQuality.lowVarianceFeatures', [])) 
                ? safeGet<string[]>(summary, 'dataQuality.lowVarianceFeatures', []).map((col: string) => (
                  <li key={col}>{col}</li>
                ))
                : <li>No low variance features found</li>
              }
            </ul>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="variable-insights" className="border rounded-lg mb-4 overflow-hidden">
          <AccordionTrigger className="bg-green-50 hover:bg-green-100 px-4 py-3 font-bold text-green-800">
            Variable Insights
          </AccordionTrigger>
          <AccordionContent className="px-4 py-3">
            <h3 className="text-md font-semibold mb-2">High Cardinality</h3>
            {renderTable(safeGet<Record<string, number>>(summary, 'variableInsights.highCardinality', {}))}

            <h3 className="text-md font-semibold mt-4 mb-2">Correlated Features</h3>
            {renderTable(safeGet<Record<string, number>>(summary, 'variableInsights.correlatedFeatures', {}))}
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="transformations" className="border rounded-lg mb-4 overflow-hidden">
          <AccordionTrigger className="bg-purple-50 hover:bg-purple-100 px-4 py-3 font-bold text-purple-800">
            Transformations
          </AccordionTrigger>
          <AccordionContent className="px-4 py-3">
            <h3 className="text-md font-semibold mb-2">Normalize</h3>
            <ul className="list-disc list-inside">
              {Array.isArray(safeGet<string[]>(summary, 'transformations.normalize', []))
                ? safeGet<string[]>(summary, 'transformations.normalize', []).map((col: string) => (
                  <li key={col}>{col}</li>
                ))
                : <li>No columns to normalize</li>
              }
            </ul>
            <h3 className="text-md font-semibold mt-4 mb-2">Encode</h3>
            <ul className="list-disc list-inside">
              {Array.isArray(safeGet<string[]>(summary, 'transformations.encode', []))
                ? safeGet<string[]>(summary, 'transformations.encode', []).map((col: string) => (
                  <li key={col}>{col}</li>
                ))
                : <li>No columns to encode</li>
              }
            </ul>
            <h3 className="text-md font-semibold mt-4 mb-2">Drop</h3>
            <ul className="list-disc list-inside">
              {Array.isArray(safeGet<string[]>(summary, 'transformations.drop', []))
                ? safeGet<string[]>(summary, 'transformations.drop', []).map((col: string) => (
                  <li key={col}>{col}</li>
                ))
                : <li>No columns to drop</li>
              }
            </ul>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="grouped-insights" className="border rounded-lg mb-4 overflow-hidden">
          <AccordionTrigger className="bg-amber-50 hover:bg-amber-100 px-4 py-3 font-bold text-amber-800">
            Grouped Insights
          </AccordionTrigger>
          <AccordionContent className="px-4 py-3">
            {Object.entries(safeGet<Record<string, Record<string, number>>>(summary, 'groupedInsights', {})).length > 0
              ? Object.entries(safeGet<Record<string, Record<string, number>>>(summary, 'groupedInsights', {})).map(([col, insights]) => (
                <div key={col} className="mb-6">
                  <h3 className="text-md font-semibold mb-2">Grouped by {col}</h3>
                  <pre className="bg-gray-100 p-2 rounded text-sm overflow-x-auto">
                    {JSON.stringify(insights, null, 2)}
                  </pre>
                </div>
              ))
              : <p>No grouped insights available</p>
            }
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
} 