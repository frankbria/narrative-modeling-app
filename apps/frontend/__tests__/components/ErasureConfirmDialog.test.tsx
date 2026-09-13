import { useState } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ErasureConfirmDialog } from '@/components/settings/ErasureConfirmDialog';
import type { EraseResponse } from '@/lib/types/erasure';

function manifest(over: Partial<EraseResponse['manifest']> = {}): EraseResponse {
  const m = {
    target_type: 'user',
    target_id: 'u1',
    subject_user_id: 'u1',
    erasure_id: 'e1',
    documents_deleted: { api_keys: 1, datasets: 2 },
    s3_objects_deleted: ['datasets/u1/x.csv'],
    redis_keys_evicted: 0,
    failures: [] as string[],
    notes: [] as string[],
    idempotent_noop: false,
    completed_at: '2026-09-12T00:00:00Z',
    total_documents_deleted: 3,
    status: 'completed',
    ...over,
  };
  return { erasure_id: m.erasure_id, status: m.status, manifest: m };
}

function setup(onConfirm: () => Promise<EraseResponse>, onErased = jest.fn()) {
  render(
    <ErasureConfirmDialog
      open
      onOpenChange={jest.fn()}
      title="Delete my account and data"
      body={<span>keeps your billing records</span>}
      confirmWord="DELETE"
      onConfirm={onConfirm}
      onErased={onErased}
    />,
  );
  return { onErased };
}

describe('ErasureConfirmDialog (#482)', () => {
  it('states what is retained and gates the action behind typing the exact word (AC3/AC4)', () => {
    setup(jest.fn());
    expect(screen.getByText(/keeps your billing records/i)).toBeInTheDocument();
    const confirm = screen.getByTestId('confirm-erasure');
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'delete' } }); // wrong case
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'DELETE' } });
    expect(confirm).toBeEnabled();
  });

  it('surfaces the manifest and calls onErased on a clean erasure (AC5)', async () => {
    const onConfirm = jest.fn().mockResolvedValue(manifest({ notes: ['retained Subscription'] }));
    const { onErased } = setup(onConfirm);
    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByTestId('confirm-erasure'));

    await waitFor(() => expect(screen.getByText(/Removed 3 records/i)).toBeInTheDocument());
    expect(screen.getByText(/retained Subscription/i)).toBeInTheDocument();
    expect(onErased).toHaveBeenCalledTimes(1);
  });

  it('does NOT report success when the manifest reports a partial failure (AC5)', async () => {
    const onConfirm = jest
      .fn()
      .mockResolvedValue(manifest({ failures: ['s3 delete x: boom'], status: 'completed_with_residuals' }));
    const { onErased } = setup(onConfirm);
    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByTestId('confirm-erasure'));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/incomplete/i));
    expect(screen.queryByText(/Removed 3 records/i)).not.toBeInTheDocument();
    expect(onErased).not.toHaveBeenCalled();
  });

  it('re-arms from scratch after Cancel — typed state is reset (AC3, codex)', () => {
    function Harness() {
      const [open, setOpen] = useState(true);
      return (
        <>
          <button onClick={() => setOpen(true)}>reopen</button>
          <ErasureConfirmDialog
            open={open}
            onOpenChange={setOpen}
            title="t"
            body={<span>b</span>}
            confirmWord="DELETE"
            onConfirm={jest.fn()}
          />
        </>
      );
    }
    render(<Harness />);
    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'DELETE' } });
    expect(screen.getByTestId('confirm-erasure')).toBeEnabled();

    fireEvent.click(screen.getByText('Cancel'));
    fireEvent.click(screen.getByText('reopen'));
    // The destructive button must be disabled again — the prior "DELETE" is gone.
    expect(screen.getByTestId('confirm-erasure')).toBeDisabled();
  });

  it('shows an error when the request throws', async () => {
    const onConfirm = jest.fn().mockRejectedValue(new Error('Erasure request failed (500)'));
    const { onErased } = setup(onConfirm);
    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByTestId('confirm-erasure'));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/failed/i));
    expect(onErased).not.toHaveBeenCalled();
  });
});
