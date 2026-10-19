import type { StatItem } from '@/lib/utils';
import {
  NUMERIC_DATA_TYPES,
  type DatasetColumnStatistic,
  type DatasetStatistics,
} from '@/lib/types/api';
import type { DashboardColumn } from './chartSelection';

function textOrEmpty(value: string | null | undefined): string {
  return value ?? '';
}

function countOrZero(value: number | null | undefined): number {
  return value ?? 0;
}

// External API payload: guard against malformed (non-object) entries.
function isObject(entry: unknown): boolean {
  return entry !== null && typeof entry === 'object';
}

function payloadFieldType(dataType: string): string {
  return (NUMERIC_DATA_TYPES as readonly string[]).includes(dataType)
    ? 'numeric'
    : textOrEmpty(dataType);
}

function statFromPayload(col: DatasetColumnStatistic): StatItem {
  return {
    field_name: textOrEmpty(col.column_name),
    field_type: payloadFieldType(col.data_type),
    count: countOrZero(col.total_count),
    missing_values: countOrZero(col.null_count),
    unique_values: countOrZero(col.unique_count),
  };
}

function statFromColumn(col: DashboardColumn): StatItem {
  return {
    field_name: col.name,
    field_type: col.type,
    count: 0,
    missing_values: countOrZero(col.null_count),
    unique_values: countOrZero(col.unique_count),
  };
}

/**
 * The heatmap's StatItem entries: from the statistics payload when it has
 * column statistics, otherwise from the column list.
 */
export function correlationStats(
  statistics: DatasetStatistics | undefined,
  columns: DashboardColumn[],
): StatItem[] {
  const columnStats = statistics?.column_statistics;
  if (Array.isArray(columnStats)) return columnStats.filter(isObject).map(statFromPayload);
  return columns.map(statFromColumn);
}
