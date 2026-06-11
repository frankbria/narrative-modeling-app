'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Loader2, X } from 'lucide-react';
import { CancelTrainingResponse, modelService } from '@/lib/services/model';

interface CancelTrainingButtonProps {
  modelId: string;
  disabled?: boolean;
  onCancelled?: (response: CancelTrainingResponse) => void;
  className?: string;
}

/**
 * Cancel button for an in-flight training job.
 *
 * Opens a confirmation dialog explaining that the current algorithm finishes
 * before training stops, then calls `POST /ml/{model_id}/cancel`. Backend
 * errors (e.g. 409 when the job already finished) are shown inline in the
 * dialog so the analyst can close it without losing context.
 */
export function CancelTrainingButton({
  modelId,
  disabled = false,
  onCancelled,
  className = '',
}: CancelTrainingButtonProps) {
  const [open, setOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) setError(null);
  };

  const handleConfirm = async () => {
    setIsCancelling(true);
    setError(null);
    try {
      const response = await modelService.cancelTraining(modelId);
      setOpen(false);
      onCancelled?.(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel training');
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <>
      <Button
        variant="outline"
        disabled={disabled}
        onClick={() => setOpen(true)}
        className={`text-red-600 hover:text-red-700 ${className}`}
      >
        <X className="w-4 h-4 mr-2" />
        Cancel Training
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel training?</DialogTitle>
            <DialogDescription>
              The current algorithm will finish, then training stops. Results from
              already-trained algorithms are kept.
            </DialogDescription>
          </DialogHeader>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isCancelling}
            >
              Keep Training
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirm}
              disabled={isCancelling}
            >
              {isCancelling && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Yes, cancel training
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default CancelTrainingButton;
