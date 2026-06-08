import { NextResponse } from 'next/server'
import ExcelJS from 'exceljs'
import { parse } from 'csv-parse/sync'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type CellPrimitive = string | number | boolean | null

/**
 * Coerce an ExcelJS cell value into a JSON-safe primitive for preview display.
 * ExcelJS surfaces dates as `Date`, and formula/hyperlink/rich-text/error cells
 * as objects, so they are flattened to a string|number|boolean|null.
 */
function normalizeCell(value: unknown): CellPrimitive {
  if (value === null || value === undefined) return null
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value
  }
  if (value instanceof Date) return value.toISOString()
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if ('result' in obj) return normalizeCell(obj.result) // formula with cached result
    if ('formula' in obj || 'sharedFormula' in obj) return null // formula without a cached value
    if ('richText' in obj && Array.isArray(obj.richText)) {
      return (obj.richText as Array<{ text?: string }>).map((rt) => rt.text ?? '').join('')
    }
    if ('text' in obj) return normalizeCell(obj.text) // hyperlink cell
    if ('error' in obj) return String(obj.error) // error cell
  }
  return String(value)
}

export async function POST(request: Request) {
  try {
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
    let previewData: CellPrimitive[][] = []

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
      const workbook = new ExcelJS.Workbook()
      // ExcelJS accepts an ArrayBuffer at runtime; its typings only declare Buffer,
      // so cast to the load() parameter type to bridge the ArrayBuffer/Buffer gap.
      await workbook.xlsx.load(buffer as unknown as Parameters<typeof workbook.xlsx.load>[0])
      const worksheet = workbook.worksheets[0]

      if (!worksheet || worksheet.rowCount === 0) {
        return NextResponse.json({ error: 'File is empty' }, { status: 400 })
      }

      // Restrict to the sheet's used column range so a blank leading column
      // doesn't shift every column (row.values is 1-indexed and pads leading
      // empties with null). Matches the previous sheet_to_json behavior.
      const dimensions = worksheet.dimensions
      const firstCol = dimensions?.left ?? 1
      const lastCol = dimensions?.right ?? worksheet.columnCount

      // Build a dense, rectangular array-of-arrays, skipping fully-empty rows so
      // blank separator rows don't consume preview slots.
      const rows: CellPrimitive[][] = []
      worksheet.eachRow({ includeEmpty: true }, (row) => {
        const values = row.values as unknown[]
        const rowData: CellPrimitive[] = []
        for (let col = firstCol; col <= lastCol; col++) {
          rowData.push(normalizeCell(values[col]))
        }
        if (rowData.some((cell) => cell !== null)) {
          rows.push(rowData)
        }
      })

      if (rows.length === 0) {
        return NextResponse.json({ error: 'File is empty' }, { status: 400 })
      }

      headers = rows[0].map((cell) => (cell === null ? '' : String(cell)))
      previewData = rows.slice(1, 11)
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