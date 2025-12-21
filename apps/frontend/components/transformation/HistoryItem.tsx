import { HistoryEntry } from '@/lib/types/history';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';

interface HistoryItemProps {
  entry: HistoryEntry;
  isCurrent: boolean;
  onClick: () => void;
}

/**
 * Individual history entry component
 *
 * Displays a single transformation in the history list with:
 * - Transformation type and description
 * - Affected columns as badges
 * - Rows affected count
 * - Relative timestamp
 * - Current state highlighting
 */
export function HistoryItem({ entry, isCurrent, onClick }: HistoryItemProps) {
  return (
    <div
      className={`
        p-3 rounded-lg cursor-pointer transition-colors
        ${isCurrent ? 'bg-primary/10 border-2 border-primary' : 'bg-muted hover:bg-muted/70'}
      `}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm">{entry.transformationType}</span>
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
        </span>
      </div>

      <p className="text-sm text-muted-foreground mb-2">{entry.description}</p>

      {entry.affectedColumns.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {entry.affectedColumns.map(col => (
            <Badge key={col} variant="outline" className="text-xs">
              {col}
            </Badge>
          ))}
        </div>
      )}

      {entry.rowsAffected !== undefined && (
        <p className="text-xs text-muted-foreground">
          {entry.rowsAffected} rows affected
        </p>
      )}
    </div>
  );
}
