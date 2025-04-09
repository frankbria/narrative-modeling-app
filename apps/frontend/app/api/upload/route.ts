import { NextResponse } from 'next/server'
import { auth } from '@clerk/nextjs/server'
import * as XLSX from 'xlsx'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type CellValue = string | number | boolean | null
type RowData = CellValue[]

export async function POST(request: Request) {
  try {
    console.log('API route called')
    const { userId } = await auth()
    console.log('User ID:', userId)
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const formData = await request.formData()
    const file = formData.get('file') as File
    
    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 })
    }

    console.log('File received:', file.name, file.type)
    const buffer = await file.arrayBuffer()
    let data: RowData[] = []
    let headers: string[] = []

    // Parse based on file type
    if (file.name.endsWith('.xlsx')) {
      console.log('Processing Excel file')
      const workbook = XLSX.read(buffer)
      const worksheet = workbook.Sheets[workbook.SheetNames[0]]
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
      data = jsonData as RowData[]
    } else if (file.name.endsWith('.csv') || file.name.endsWith('.txt')) {
      console.log('Processing CSV/TXT file')
      const text = new TextDecoder().decode(buffer)
      // Try different delimiters
      const delimiters = [',', '\t', '|', ';']
      let parsedData: string[][] = []
      let foundValidDelimiter = false
      
      for (const delimiter of delimiters) {
        const lines = text.split('\n')
        parsedData = lines.map(line => line.split(delimiter))
        if (parsedData[0].length > 1) {
          console.log('Found delimiter:', delimiter)
          foundValidDelimiter = true
          break // Found a valid delimiter
        }
      }
      
      if (!foundValidDelimiter) {
        return NextResponse.json({ error: 'Could not detect a valid delimiter in the file' }, { status: 400 })
      }
      
      data = parsedData as RowData[]
    } else {
      return NextResponse.json({ error: 'Unsupported file type' }, { status: 400 })
    }

    // Check if we have data
    if (data.length === 0) {
      return NextResponse.json({ error: 'File is empty' }, { status: 400 })
    }

    // Extract headers and first 10 rows
    headers = data[0] as string[]
    const previewData = data.slice(1, 11)
    console.log('Headers:', headers)
    console.log('Preview data rows:', previewData.length)

    // Validate headers
    if (headers.length === 0) {
      return NextResponse.json({ error: 'No headers found in the file' }, { status: 400 })
    }

    // Ensure all rows have the same number of columns as headers
    const validPreviewData = previewData.map(row => {
      // If row has fewer columns than headers, pad with null
      if (row.length < headers.length) {
        return [...row, ...Array(headers.length - row.length).fill(null)]
      }
      // If row has more columns than headers, truncate
      return row.slice(0, headers.length)
    })

    console.log('Validated preview data:', validPreviewData)

    const responseData = {
      headers,
      previewData: validPreviewData,
      fileName: file.name,
      fileType: file.type
    }

    console.log('Sending response:', JSON.stringify(responseData, null, 2))
    return NextResponse.json(responseData)
  } catch (error) {
    console.error('Error processing file:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Error processing file' },
      { status: 500 }
    )
  }
} 