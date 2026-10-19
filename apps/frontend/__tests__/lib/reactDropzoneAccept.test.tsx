/**
 * #442 (P2.2 companion): guard that react-dropzone still accepts the upload page's
 * file types under the 19.3.0 bump (whose sole feature was "group MIME types in
 * accept"). The e2e upload path is the full check; this is the hermetic regression
 * test the issue asks for (AC5) so a future dropzone bump that silently rejects a
 * valid .csv fails a unit test instead of only the e2e suite.
 *
 * The accept map is the one UploadDropzone passes to useDropzone (#1109): CSV and Excel,
 * the formats the upload routes read.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useDropzone } from 'react-dropzone'
import { ACCEPT } from '@/components/upload/UploadDropzone'

function Dropzone({ onDrop }: { onDrop: (a: File[]) => void }) {
  const { getRootProps, getInputProps } = useDropzone({ onDrop, accept: ACCEPT, multiple: false })
  return (
    <div {...getRootProps()} data-testid="dz">
      <input {...getInputProps()} />
      drop here
    </div>
  )
}

function dropEvent(file: File) {
  return {
    dataTransfer: {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    },
  }
}

async function accepts(file: File): Promise<boolean> {
  const onDrop = jest.fn()
  render(<Dropzone onDrop={onDrop} />)
  fireEvent.drop(screen.getByTestId('dz'), dropEvent(file))
  await waitFor(() => expect(onDrop).toHaveBeenCalled())
  const acceptedFiles: File[] = onDrop.mock.calls[0][0]
  return acceptedFiles.length === 1
}

describe('react-dropzone 19.3.0 accepts the upload page file types (#442)', () => {
  it('accepts a .csv', async () => {
    expect(await accepts(new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' }))).toBe(true)
  })

  it('accepts an .xlsx', async () => {
    expect(
      await accepts(
        new File(['x'], 'data.xlsx', {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }),
      ),
    ).toBe(true)
  })

  it('accepts an .xls', async () => {
    expect(
      await accepts(new File(['x'], 'data.xls', { type: 'application/vnd.ms-excel' })),
    ).toBe(true)
  })

  it('refuses a .json, which the upload routes answer 400 (#1109)', async () => {
    expect(await accepts(new File(['{}'], 'data.json', { type: 'application/json' }))).toBe(false)
  })

  it('refuses a .txt, which the upload routes answer 400 (#1109)', async () => {
    expect(await accepts(new File(['a,b\n1,2\n'], 'data.txt', { type: 'text/plain' }))).toBe(false)
  })

  it('rejects an unsupported type (.png)', async () => {
    expect(await accepts(new File(['x'], 'img.png', { type: 'image/png' }))).toBe(false)
  })
})
