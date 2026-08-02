'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Share2, CheckCircle, AlertCircle } from 'lucide-react';
import { TransformationService } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';

interface RecipeShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recipeId: string;
  recipeName: string;
}

export function RecipeShareDialog({
  open,
  onOpenChange,
  recipeId,
  recipeName
}: RecipeShareDialogProps) {
  const [targetUserId, setTargetUserId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleShare = async () => {
    if (!targetUserId.trim()) {
      setError('Please enter a user ID');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const token = await getAuthToken();
      const result = await TransformationService.shareRecipe(
        recipeId,
        targetUserId.trim(),
        token
      );

      setSuccess(result.message);
      setTargetUserId('');

      setTimeout(() => {
        onOpenChange(false);
        setSuccess(null);
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to share recipe');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setTargetUserId('');
    setError(null);
    setSuccess(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Share2 className="w-5 h-5" />
            Share Recipe
          </DialogTitle>
          <DialogDescription>
            Share &quot;{recipeName}&quot; with another user. They will receive an independent copy.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="userId">User ID</Label>
            <Input
              id="userId"
              placeholder="Enter recipient's user ID"
              value={targetUserId}
              onChange={(e) => setTargetUserId(e.target.value)}
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">
              The user must be registered in the system
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {success && (
            <Alert className="bg-green-50 dark:bg-green-950/40 text-green-900 dark:text-green-200 border-green-200 dark:border-green-900">
              <CheckCircle className="h-4 w-4" />
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="sm:justify-between">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleShare}
            disabled={loading || !targetUserId.trim()}
          >
            {loading ? (
              <>
                <span className="animate-spin mr-2">⏳</span>
                Sharing...
              </>
            ) : (
              <>
                <Share2 className="w-4 h-4 mr-2" />
                Share Recipe
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
