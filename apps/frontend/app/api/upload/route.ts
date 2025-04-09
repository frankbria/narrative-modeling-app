import { NextResponse } from 'next/server'
import * as XLSX from 'xlsx'
import { parse } from 'csv-parse/sync'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(request: Request) {
  try {
    console.log('API route called')

    // Get the form data from the request
    const formData = await request.formData()
    const file = formData.get('file') as File
    
    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 })
    }

    // Read the file content
    const buffer = await file.arrayBuffer()
    const fileType = file.name.split('.').pop()?.toLowerCase()
    
    let headers: string[] = []
    let previewData: (string | number | boolean | null)[][] = []

    // Process based on file type
    if (fileType === 'csv' || fileType === 'txt') {
      const content = new TextDecoder().decode(buffer)
      const records = parse(content, {
        columns: true,
        skip_empty_lines: true,
        trim: true
      })
      
      if (records.length === 0) {
        return NextResponse.json({ error: 'File is empty' }, { status: 400 })
      }

      headers = Object.keys(records[0])
      previewData = records.slice(0, 10).map((record: Record<string, string | number | boolean | null>) => 
        headers.map(header => record[header] ?? null)
      )
    } else if (fileType === 'xlsx') {
      const workbook = XLSX.read(buffer, { type: 'buffer' })
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
      const data = XLSX.utils.sheet_to_json(firstSheet, { header: 1 })
      
      if (data.length === 0) {
        return NextResponse.json({ error: 'File is empty' }, { status: 400 })
      }

      headers = data[0] as string[]
      previewData = data.slice(1, 11) as (string | number | boolean | null)[][]
    } else {
      return NextResponse.json(
        { error: 'Unsupported file type' },
        { status: 400 }
      )
    }

    return NextResponse.json({
      headers,
      previewData,
      fileName: file.name,
      fileType
    })
    
  } catch (error) {
    console.error('Error processing file:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
} 