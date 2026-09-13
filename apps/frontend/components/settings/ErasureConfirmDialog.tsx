'use client';

/**
 * Irreversible-erasure confirmation dialog (#482). Used for both "delete my
 * account and data" and per-dataset erase. Requires typing an exact confirmation
 * word (AC3), states plainly what is deleted vs retained (AC4), and surfaces the
 * returned manifest — refusing to report success when the cascade reports a
 * partial failure (AC5).
 */
import { useState, type ReactNode } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { hasResiduals, type DeletionManifest, type EraseResponse } from '@/lib/types/erasure';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Plain statement of what is deleted and what is retained (AC4). */
  body: ReactNode;
  /** Exact word the user must type to enable the destructive action (AC3). */
  confirmWord: string;
  /** Runs the erasure and returns its manifest. */
  onConfirm: () => Promise<EraseResponse>;
  /** Called after a clean (no-residual) erasure completes. */
  onErased?: (manifest: DeletionManifest) => void;
  confirmLabel?: string;
}

export function ErasureConfirmDialog({
  open,
  onOpenChange,
  title,
  body,
  confirmWord,
  onConfirm,
  onErased,
  confirmLabel = 'Delete permanently',
}: Props) {
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DeletionManifest | null>(null);

  const armed = typed === confirmWord && !busy;

  function reset() {
    setTyped('');
    setBusy(false);
    setError(null);
    setResult(null);
  }

  async function handleConfirm() {
    setBusy(true);
    setError(null);
    try {
      const { manifest } = await onConfirm();
      if (hasResiduals(manifest)) {
        // AC5: a manifest with failures is NOT success. Show what failed and
        // tell the user it can be safely retried (the cascade is idempotent).
        setError(
          `Erasure was incomplete: ${manifest.failures.length} step(s) failed. ` +
            'Your data has been partially removed; please retry to finish.',
        );
        setResult(manifest);
      } else {
        setResult(manifest);
        onErased?.(manifest);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erasure request failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  const cleanlyDone = result !== null && !hasResiduals(result);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription asChild>
            <div className="text-sm text-muted-foreground">{body}</div>
          </DialogDescription>
        </DialogHeader>

        {cleanlyDone ? (
          <Alert>
            <AlertDescription>
              Done. Removed {result.total_documents_deleted} record
              {result.total_documents_deleted === 1 ? '' : 's'}
              {result.s3_objects_deleted.length > 0
                ? ` and ${result.s3_objects_deleted.length} stored file(s)`
                : ''}
              .
              {result.notes.length > 0 ? ` ${result.notes.join(' ')}` : ''}
            </AlertDescription>
          </Alert>
        ) : (
          <>
            {error && (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <label htmlFor="erasure-confirm" className="text-sm font-medium text-foreground">
                Type <span className="font-mono font-semibold">{confirmWord}</span> to confirm
              </label>
              <input
                id="erasure-confirm"
                type="text"
                autoComplete="off"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
          </>
        )}

        <DialogFooter>
          {cleanlyDone ? (
            <Button onClick={() => onOpenChange(false)}>Close</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleConfirm}
                disabled={!armed}
                data-testid="confirm-erasure"
              >
                {busy ? 'Deleting…' : error ? 'Retry' : confirmLabel}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
