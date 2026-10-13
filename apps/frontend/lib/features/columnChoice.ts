/**
 * What the Feature Engineering stage records, and what training does with it (#969).
 *
 * The stage is a choice of columns the model may learn from. It is kept as both
 * halves: `selectedFeatures` is what the stage validation reads, `excludedFeatures`
 * is what training is told to leave out. Recording the excluded half means a column
 * the dataset gains later is used by default, as it would be with no choice made.
 */

export interface ColumnChoice {
  selectedFeatures: string[];
  excludedFeatures: string[];
}

function names(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  return value.every((item) => typeof item === 'string') ? value : null;
}

/** The choice a completed stage holds, or null when none was recorded. */
export function recordedChoice(stageData: unknown): ColumnChoice | null {
  const data = (stageData ?? {}) as Record<string, unknown>;
  const selectedFeatures = names(data.selectedFeatures);
  if (!selectedFeatures) return null;
  return { selectedFeatures, excludedFeatures: names(data.excludedFeatures) ?? [] };
}

export function choiceOf(columns: string[], selected: string[]): ColumnChoice {
  return {
    selectedFeatures: columns.filter((column) => selected.includes(column)),
    excludedFeatures: columns.filter((column) => !selected.includes(column)),
  };
}

/** Every column, less the ones a recorded choice left out. */
export function startingSelection(columns: string[], recorded: ColumnChoice | null): string[] {
  const leftOut = recorded?.excludedFeatures ?? [];
  return columns.filter((column) => !leftOut.includes(column));
}

export function sameChoice(recorded: ColumnChoice | null, selected: string[]): boolean {
  if (!recorded) return false;
  const kept = recorded.selectedFeatures;
  return kept.length === selected.length && kept.every((column) => selected.includes(column));
}

/** The columns training must leave out. The target is never a feature, so it is never listed. */
export function excludedFromTraining(stageData: unknown, targetColumn: string): string[] {
  const leftOut = recordedChoice(stageData)?.excludedFeatures ?? [];
  return leftOut.filter((column) => column !== targetColumn);
}
