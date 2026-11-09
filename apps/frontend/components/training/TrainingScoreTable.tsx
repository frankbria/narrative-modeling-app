import React from 'react';
import { HugeiconsIcon } from '@hugeicons/react';
import { InformationCircleIcon } from '@hugeicons/core-free-icons';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { ModelComparisonEntry, TrainingStatus } from '@/lib/services/model';

// Keyed `${chosen}-${highestTest}`: the chosen model follows the cross-validation score.
const VERDICTS: Record<string, string> = {
  'true-true': 'Chosen: best on both checks.',
  'true-false':
    'Chosen for the steadiest cross-validation score; another model scored higher on the test rows.',
  'false-true':
    'Scored highest on the test rows, but its cross-validation score was lower, so it was not chosen.',
  'false-false': 'Trailed the chosen model.',
};

const CV_HINT =
  'Cross-validation: the training rows are split several ways, the model is scored on each held-back part, and the scores are averaged. Models are ranked by this.';
const TEST_HINT =
  'Test score: the model scored once on rows kept aside before training. A single check, so it can favour a different model than cross-validation.';

const ROW_STYLE: Record<string, string> = { true: 'bg-warning/10 font-medium', false: '' };

function highestTest(rows: ModelComparisonEntry[]): number {
  return Math.max(...rows.map((row) => row.test_score ?? -Infinity));
}

export function verdictFor(row: ModelComparisonEntry, status: TrainingStatus): string {
  const chosen = row.algorithm === status.best_algorithm;
  const top = row.test_score != null && row.test_score === highestTest(status.model_comparison);
  return VERDICTS[`${chosen}-${top}`];
}

const formatScore = (score?: number | null) => (score != null ? score.toFixed(3) : '—');

function HeadingWithHint(props: { label: string; hint: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      {props.label}
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={`What is the ${props.label}?`}
            className="rounded-full text-muted-foreground transition-all hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <HugeiconsIcon icon={InformationCircleIcon} className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{props.hint}</TooltipContent>
      </Tooltip>
    </span>
  );
}

function ScoreRow(props: { row: ModelComparisonEntry; status: TrainingStatus }) {
  const { row, status } = props;
  return (
    <tr className={ROW_STYLE[String(row.algorithm === status.best_algorithm)]}>
      <td className="py-2 pr-4 align-top">{row.algorithm}</td>
      <td className="py-2 pr-4 align-top">{formatScore(row.cv_score)}</td>
      <td className="py-2 pr-4 align-top">{formatScore(row.test_score)}</td>
      <td className="py-2 align-top text-muted-foreground">{verdictFor(row, status)}</td>
    </tr>
  );
}

/** Every model that ran, its two scores, and a one-line verdict on how they compare. */
export function TrainingScoreTable(props: { status: TrainingStatus }) {
  const { status } = props;
  return (
    <TooltipProvider>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2 pr-4">Algorithm</th>
              <th className="py-2 pr-4">
                <HeadingWithHint label="CV score" hint={CV_HINT} />
              </th>
              <th className="py-2 pr-4">
                <HeadingWithHint label="Test score" hint={TEST_HINT} />
              </th>
              <th className="py-2">How it compares</th>
            </tr>
          </thead>
          <tbody>
            {status.model_comparison.map((row) => (
              <ScoreRow key={row.algorithm} row={row} status={status} />
            ))}
          </tbody>
        </table>
      </div>
    </TooltipProvider>
  );
}
