import type { DashboardColumn } from './chartSelection';

const SINGLE_COLUMN: Record<string, string> = {
  numeric: 'Histogram, Box Plot',
  categorical: 'Bar Chart',
};

type MaybeType = string | undefined;

function singleRecommendation(type: MaybeType): string[] {
  const recommendation = type ? SINGLE_COLUMN[type] : undefined;
  const found = recommendation ? [recommendation] : [];
  return found;
}

function isNumeric(type: MaybeType): boolean {
  return type === 'numeric';
}

function pairRecommendation(types: MaybeType[]): string[] {
  if (types.every(isNumeric)) return ['Scatter Plot, Line Chart'];
  const mixed = types.includes('numeric') && types.includes('categorical');
  if (mixed) return ['Box Plot (grouped), Bar Chart'];
  return [];
}

/** Chart suggestions for the selected columns, by how many there are and what they hold. */
export function chartRecommendations(selected: string[], columns: DashboardColumn[]): string[] {
  const types = selected.map(name => columns.find(col => col.name === name)?.type);
  if (selected.length === 0) return ['Select columns to see chart recommendations'];
  if (selected.length === 1) return singleRecommendation(types[0]);
  if (selected.length === 2) return pairRecommendation(types);
  return ['Line Chart, Correlation Heatmap'];
}
