import { NextResponse } from 'next/server'
import ExcelJS from 'exceljs'
import { parse } from 'csv-parse/sync'
import { auth } from '@/auth'
import { rateLimit } from '@/lib/api-guards'

// Add proper Next.js API route configuration
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

// Per-user throttle to bound parser-amplification abuse.
const UPLOAD_RATE_LIMIT = { limit: 30, windowMs: 60_000 }

const PREVIEW_UPLOAD_MAX_BYTES = 100 * 1024 * 1024
const PREVIEW_UPLOAD_MAX_LABEL = `${PREVIEW_UPLOAD_MAX_BYTES / (1024 * 1024)}MB`
const PREVIEW_ROW_LIMIT = 11 // header + 10 preview rows

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
    // Require an authenticated session before buffering/parsing any file.
    const session = await auth()
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Throttle per user to bound parser-amplification abuse.
    const limit = rateLimit(`upload:${session.user.id}`, UPLOAD_RATE_LIMIT)
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Too many requests' },
        { status: 429, headers: { 'Retry-After': String(Math.ceil(limit.retryAfterMs / 1000)) } }
      )
    }

    // Get the form data from the request
    const formData = await request.formData()
    const file = formData.get('file') as File

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 })
    }

    // request.formData() has already parsed the multipart body; proxy/platform
    // request-size limits remain the real memory boundary. This route guard
    // prevents allocating another ArrayBuffer for oversized preview parsing.
    if (file.size > PREVIEW_UPLOAD_MAX_BYTES) {
      return NextResponse.json(
        { error: `File exceeds the ${PREVIEW_UPLOAD_MAX_LABEL} preview limit. Use chunked upload for larger files.` },
        { status: 413 }
      )
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
        trim: true,
        to: PREVIEW_ROW_LIMIT // stop after the preview; don't scan the whole file
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

      // Use the sheet's actual used column range (like the previous
      // sheet_to_json({ header: 1 }), which keyed off the worksheet's !ref).
      // This trims genuinely-empty leading/trailing columns while preserving any
      // column that holds data even when its header cell is blank, so no data is
      // dropped. row.values is 1-indexed (values[0] is unused).
      const dimensions = worksheet.dimensions
      const firstCol = dimensions?.left ?? 1
      const lastCol = dimensions?.right ?? worksheet.columnCount

      const toRow = (values: unknown[]): CellPrimitive[] => {
        const rowData: CellPrimitive[] = []
        for (let col = firstCol; col <= lastCol; col++) {
          rowData.push(normalizeCell(values[col]))
        }
        return rowData
      }

      // Collect rows that carry content, dropping fully-empty separator rows so
      // they don't consume preview slots. We only need 11 rows (header + 10
      // preview), so read rows by index and stop once the preview is full.
      const rows: CellPrimitive[][] = []
      for (let rowNumber = 1; rowNumber <= worksheet.rowCount && rows.length < PREVIEW_ROW_LIMIT; rowNumber++) {
        const row = worksheet.getRow(rowNumber)
        const rowData = toRow(row.values as unknown[])
        if (rowData.some((cell) => cell !== null)) {
          rows.push(rowData)
        }
      }

      if (rows.length === 0) {
        return NextResponse.json({ error: 'File is empty' }, { status: 400 })
      }

      headers = rows[0].map((cell) => (cell === null ? '' : String(cell)))
      previewData = rows.slice(1, PREVIEW_ROW_LIMIT)
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
