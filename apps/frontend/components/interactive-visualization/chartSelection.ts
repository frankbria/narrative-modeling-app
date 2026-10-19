export type ColumnType = 'numeric' | 'categorical' | 'datetime' | 'text';

export interface DashboardColumn {
  name: string;
  type: ColumnType;
  unique_count?: number;
  null_count?: number;
}

/** The charts whose data the dashboard fetches itself. */
export type FetchedChart = 'boxplot' | 'scatter' | 'line';

export function isFetchedChart(chart: string): boolean {
  return chart === 'boxplot' || chart === 'scatter' || chart === 'line';
}

/** How many columns a chart can plot at once. */
export function maxColumnsFor(chart: string): number {
  if (chart === 'scatter') return 2;
  const lineOrOther = chart === 'line' ? 4 : 1;
  return lineOrOther;
}

/** Picking a column beyond the chart's limit starts the selection over with it. */
export function toggleColumn(selected: string[], name: string, chart: string): string[] {
  if (selected.includes(name)) return selected.filter(selectedName => selectedName !== name);
  const next = selected.length >= maxColumnsFor(chart) ? [name] : [...selected, name];
  return next;
}

/** With nothing chosen, the first numeric column stands in for the choice. */
export function withDefaultSelection(
  chosen: string[],
  numericColumns: DashboardColumn[],
): string[] {
  const selection =
    chosen.length === 0 && numericColumns.length > 0 ? [numericColumns[0].name] : chosen;
  return selection;
}

/** Whether the selection meets what the chart needs; otherwise nothing is fetched or invented. */
export function canFetchChart(
  chart: string,
  numericSelected: string[],
  lineX: string | undefined,
  lineY: string[],
): boolean {
  if (chart === 'boxplot') return numericSelected.length >= 1;
  if (chart === 'scatter') return numericSelected.length >= 2;
  return lineX !== undefined && lineY.length >= 1;
}

export function chartTitle(chart: string): string {
  return chart.charAt(0).toUpperCase() + chart.slice(1);
}

export function columnsOfType(columns: DashboardColumn[], type: ColumnType): DashboardColumn[] {
  return columns.filter(col => col.type === type);
}
