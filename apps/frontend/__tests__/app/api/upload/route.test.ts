/**
 * @jest-environment node
 *
 * Tests for the file-upload parsing route (`app/api/upload/route.ts`).
 *
 * These are characterization/regression tests guarding the parsing contract
 * across the xlsx -> exceljs migration (issue #165). They exercise the route
 * end-to-end using Node's native File/FormData/Request, generating real .xlsx
 * fixtures with exceljs (no mocking).
 */
import ExcelJS from 'exceljs'
import { POST } from '@/app/api/upload/route'

/** Build a real .xlsx buffer from rows (first row treated as header by the route). */
async function makeXlsxFile(rows: (string | number | boolean)[][], name = 'data.xlsx'): Promise<File> {
  const workbook = new ExcelJS.Workbook()
  const sheet = workbook.addWorksheet('Sheet1')
  rows.forEach((row) => sheet.addRow(row))
  const buffer = await workbook.xlsx.writeBuffer()
  return new File([buffer], name, {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}

function makeTextFile(content: string, name: string, type = 'text/plain'): File {
  return new File([content], name, { type })
}

function makeRequest(file?: File): Request {
  const formData = new FormData()
  if (file) formData.append('file', file)
  return new Request('http://localhost/api/upload', { method: 'POST', body: formData })
}

describe('POST /api/upload', () => {
  describe('.xlsx parsing', () => {
    it('parses headers and preview rows from an .xlsx file', async () => {
      const file = await makeXlsxFile([
        ['name', 'age', 'active'],
        ['Alice', 30, true],
        ['Bob', 25, false],
      ])

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(200)

      const body = await res.json()
      expect(body.headers).toEqual(['name', 'age', 'active'])
      expect(body.previewData).toEqual([
        ['Alice', 30, true],
        ['Bob', 25, false],
      ])
      expect(body.fileName).toBe('data.xlsx')
      expect(body.fileType).toBe('xlsx')
    })

    it('caps preview rows at 10', async () => {
      const rows: (string | number)[][] = [['col']]
      for (let i = 0; i < 15; i++) rows.push([`v${i}`])

      const res = await POST(makeRequest(await makeXlsxFile(rows)))
      const body = await res.json()

      expect(res.status).toBe(200)
      expect(body.headers).toEqual(['col'])
      expect(body.previewData).toHaveLength(10)
      expect(body.previewData[0]).toEqual(['v0'])
      expect(body.previewData[9]).toEqual(['v9'])
    })

    it('normalizes complex cell types (date, formula, hyperlink, rich text) to primitives', async () => {
      const workbook = new ExcelJS.Workbook()
      const sheet = workbook.addWorksheet('Sheet1')
      sheet.addRow(['date', 'formula', 'hyperlink', 'rich', 'uncomputed'])
      const row = sheet.addRow([])
      row.getCell(1).value = new Date('2024-01-15T12:00:00.000Z')
      row.getCell(2).value = { formula: 'A1', result: 99 }
      row.getCell(3).value = { text: 'click here', hyperlink: 'https://example.com' }
      row.getCell(4).value = { richText: [{ text: 'Hello ' }, { text: 'World' }] }
      row.getCell(5).value = { formula: '1+1' } // formula with no cached result
      const buffer = await workbook.xlsx.writeBuffer()
      const file = new File([buffer], 'complex.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(200)

      const body = await res.json()
      const [dateCell, formulaCell, hyperlinkCell, richCell, uncomputedCell] = body.previewData[0]
      expect(typeof dateCell).toBe('string')
      expect(dateCell).toMatch(/^2024-01-15T/) // Date -> ISO string
      expect(formulaCell).toBe(99) // formula -> result
      expect(hyperlinkCell).toBe('click here') // hyperlink -> text
      expect(richCell).toBe('Hello World') // rich text -> concatenated text
      expect(uncomputedCell).toBeNull() // uncached formula -> null (not "[object Object]")
    })

    it('trims a leading empty column so columns are not shifted', async () => {
      const workbook = new ExcelJS.Workbook()
      const sheet = workbook.addWorksheet('Sheet1')
      // Data starts in column B; column A is entirely blank.
      sheet.getCell('B1').value = 'h1'
      sheet.getCell('C1').value = 'h2'
      sheet.getCell('B2').value = 'x'
      sheet.getCell('C2').value = 'y'
      const buffer = await workbook.xlsx.writeBuffer()
      const file = new File([buffer], 'offset.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(200)

      const body = await res.json()
      expect(body.headers).toEqual(['h1', 'h2'])
      expect(body.previewData).toEqual([['x', 'y']])
    })

    it('skips fully-blank interior rows', async () => {
      const file = await makeXlsxFile([
        ['h1', 'h2'],
        ['a', 'b'],
        [], // blank separator row
        ['c', 'd'],
      ])

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(200)

      const body = await res.json()
      expect(body.headers).toEqual(['h1', 'h2'])
      expect(body.previewData).toEqual([
        ['a', 'b'],
        ['c', 'd'],
      ])
    })

    it('preserves a populated column even when its header cell is blank', async () => {
      const workbook = new ExcelJS.Workbook()
      const sheet = workbook.addWorksheet('Sheet1')
      // Column A has data but no header; column B is fully labelled.
      sheet.getCell('B1').value = 'name'
      sheet.getCell('A2').value = 123
      sheet.getCell('B2').value = 'Alice'
      const buffer = await workbook.xlsx.writeBuffer()
      const file = new File([buffer], 'blank-header.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(200)

      const body = await res.json()
      // Column A is kept (blank header -> ''); its data is not dropped.
      expect(body.headers).toEqual(['', 'name'])
      expect(body.previewData).toEqual([[123, 'Alice']])
    })

    it('returns 400 for an empty .xlsx file', async () => {
      const workbook = new ExcelJS.Workbook()
      workbook.addWorksheet('Sheet1') // no rows
      const buffer = await workbook.xlsx.writeBuffer()
      const file = new File([buffer], 'empty.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(400)
      expect((await res.json()).error).toBe('File is empty')
    })
  })

  describe('.csv parsing (regression guard)', () => {
    it('parses headers and preview rows from a .csv file', async () => {
      const file = makeTextFile('name,age\nAlice,30\nBob,25\n', 'data.csv', 'text/csv')

      const res = await POST(makeRequest(file))
      expect(res.status).toBe(200)

      const body = await res.json()
      expect(body.headers).toEqual(['name', 'age'])
      expect(body.previewData).toEqual([
        ['Alice', '30'],
        ['Bob', '25'],
      ])
      expect(body.fileType).toBe('csv')
    })
  })

  describe('error handling', () => {
    it('returns 400 when no file is provided', async () => {
      const res = await POST(makeRequest())
      expect(res.status).toBe(400)
      expect((await res.json()).error).toBe('No file provided')
    })

    it('returns 400 for an unsupported file type', async () => {
      const res = await POST(makeRequest(makeTextFile('{}', 'data.json', 'application/json')))
      expect(res.status).toBe(400)
      expect((await res.json()).error).toBe('Unsupported file type')
    })
  })
})
