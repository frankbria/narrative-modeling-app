'use client';

import { HistoryEntry } from '@/lib/types/history';
import { HistoryItem } from './HistoryItem';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { HugeiconsIcon } from '@hugeicons/react';
import { Delete02Icon } from '@hugeicons/core-free-icons';

interface TransformationHistoryProps {
  datasetId: string;
  history: HistoryEntry[];
  currentPosition: number;
  onJumpToPosition: (position: number) => void;
  onClearHistory: () => void;
}

/**
 * Transformation history panel
 *
 * Displays a list of all transformations applied to a dataset with:
 * - Scrollable list of history entries
 * - Current position highlighting
 * - Jump to position functionality
 * - Clear history button
 * - Transformation count display
 */
export function TransformationHistory({
  datasetId,
  history,
  currentPosition,
  onJumpToPosition,
  onClearHistory
}: TransformationHistoryProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <h3 className="font-semibold text-lg">Transformation History</h3>
        <p className="text-sm text-muted-foreground">
          {history.length} transformation{history.length !== 1 ? 's' : ''}
        </p>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="space-y-2">
          {history.map((entry, index) => (
            <HistoryItem
              key={index}
              entry={entry}
              isCurrent={index === currentPosition}
              onClick={() => onJumpToPosition(index)}
            />
          ))}
        </div>
      </ScrollArea>

      {history.length > 0 && (
        <div className="p-4 border-t">
          <Button
            variant="destructive"
            size="sm"
            onClick={onClearHistory}
            className="w-full"
          >
            <HugeiconsIcon icon={Delete02Icon} className="h-4 w-4 mr-2" />
            Clear History
          </Button>
        </div>
      )}
    </div>
  );
}
