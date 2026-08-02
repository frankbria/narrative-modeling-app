'use client';

import React, { useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Download, Copy, CheckCircle, AlertCircle } from 'lucide-react';
import { TransformationService } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';

interface RecipeExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recipeId: string;
  recipeName: string;
}

export function RecipeExportDialog({
  open,
  onOpenChange,
  recipeId,
  recipeName
}: RecipeExportDialogProps) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const { data: jsonData, loading, error: loadError } = useAsyncData(
    async () => {
      const token = await getAuthToken();
      const result = await TransformationService.exportRecipeAsJSON(recipeId, token);
      return JSON.stringify(result, null, 2);
    },
    [open, recipeId],
    // Only fetch while the dialog is open, replacing `if (open && !jsonData)`.
    { enabled: open },
  );

  const error = copyError ?? loadError;

  const handleDownload = () => {
    if (!jsonData) return;

    const blob = new Blob([jsonData], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${recipeName.replace(/\s+/g, '_')}_recipe.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    if (!jsonData) return;

    try {
      await navigator.clipboard.writeText(jsonData);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError('Failed to copy to clipboard');
    }
  };

  const handleClose = () => {
    // jsonData and the load error used to be cleared here; both are keyed on
    // `open` now, so closing discards them without an explicit reset.
    setCopyError(null);
    setCopied(false);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="w-5 h-5" />
            Export Recipe
          </DialogTitle>
          <DialogDescription>
            Export &quot;{recipeName}&quot; as JSON for portability and version control
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {loading && (
            <div className="flex items-center justify-center py-8" role="status">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {jsonData && !loading && (
            <Tabs defaultValue="preview" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="preview">Preview</TabsTrigger>
                <TabsTrigger value="formatted">Formatted</TabsTrigger>
              </TabsList>

              <TabsContent value="preview" className="mt-4">
                <div className="relative">
                  <pre className="bg-muted p-4 rounded-lg overflow-auto max-h-96 text-xs font-mono">
                    {jsonData}
                  </pre>
                </div>
              </TabsContent>

              <TabsContent value="formatted" className="mt-4">
                <div className="space-y-3">
                  <div className="bg-blue-50 dark:bg-blue-950/40 p-3 rounded-lg">
                    <p className="text-sm font-medium text-blue-900 dark:text-blue-200">Recipe Format</p>
                    <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                      This JSON file contains the complete recipe definition including all transformation steps,
                      metadata, and version information. You can import this file into any compatible system.
                    </p>
                  </div>
                  <div className="bg-muted p-4 rounded-lg">
                    <p className="text-xs text-muted-foreground">
                      <strong>File name:</strong> {recipeName.replace(/\s+/g, '_')}_recipe.json
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      <strong>Size:</strong> {new Blob([jsonData]).size} bytes
                    </p>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          )}

          {copied && (
            <Alert className="bg-green-50 dark:bg-green-950/40 text-green-900 dark:text-green-200 border-green-200 dark:border-green-900">
              <CheckCircle className="h-4 w-4" />
              <AlertDescription>Copied to clipboard!</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="sm:justify-between">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
          >
            Close
          </Button>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleCopy}
              disabled={!jsonData || loading}
            >
              <Copy className="w-4 h-4 mr-2" />
              Copy JSON
            </Button>
            <Button
              type="button"
              onClick={handleDownload}
              disabled={!jsonData || loading}
            >
              <Download className="w-4 h-4 mr-2" />
              Download
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
