import React from 'react';
import { excludedFromTraining } from '@/lib/features/columnChoice';

interface LeftOutColumnsProps {
  /** What the Feature Engineering stage recorded. */
  stageData: unknown;
  targetColumn: string;
}

/** Before a run starts: the columns the user left out, so what the model sees is no surprise (#969). */
export function LeftOutColumns(props: LeftOutColumnsProps) {
  const { stageData, targetColumn } = props;
  const columns = excludedFromTraining(stageData, targetColumn);
  if (columns.length === 0) return null;
  return (
    <p data-testid="left-out-columns" className="text-sm text-muted-foreground mb-4">
      Left out in Feature Engineering, so the model will not see them:{' '}
      <span className="font-mono text-foreground">{columns.join(', ')}</span>
    </p>
  );
}
