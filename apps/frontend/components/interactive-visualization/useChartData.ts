import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { getAuthToken } from '@/lib/auth-helpers';
import {
  getBoxPlot,
  getLineChart,
  getScatterPlot,
  type BoxPlotData,
  type LineChartData,
  type ScatterPlotData,
} from '@/lib/services/visualization';
import type { ChartFilter } from '../ChartControls';
import { canFetchChart, isFetchedChart, type DashboardColumn } from './chartSelection';

type ChartResult =
  | { kind: 'boxplot'; data: BoxPlotData }
  | { kind: 'scatter'; data: ScatterPlotData }
  | { kind: 'line'; data: LineChartData };

export interface ChartRequest {
  activeChart: string;
  datasetId: string;
  columns: DashboardColumn[];
  selectedColumns: string[];
  numericSelected: string[];
  lineX: string;
  lineY: string[];
  filters: ChartFilter[];
  refreshKey: number;
}

export async function authToken(): Promise<string | undefined> {
  return (await getAuthToken()) ?? undefined;
}

async function loadChart(request: ChartRequest): Promise<ChartResult> {
  const { activeChart, datasetId, filters, numericSelected, lineX, lineY } = request;
  const token = await authToken();
  if (activeChart === 'boxplot') {
    return { kind: 'boxplot', data: await getBoxPlot(datasetId, numericSelected[0], token) };
  }
  if (activeChart === 'scatter') {
    return {
      kind: 'scatter',
      data: await getScatterPlot(datasetId, numericSelected[0], numericSelected[1], filters, token),
    };
  }
  return { kind: 'line', data: await getLineChart(datasetId, lineX, lineY, filters, token) };
}

function fetchEnabled(request: ChartRequest): boolean {
  const { activeChart, datasetId, numericSelected, lineX, lineY } = request;
  return (
    isFetchedChart(activeChart) &&
    !!datasetId &&
    canFetchChart(activeChart, numericSelected, lineX, lineY)
  );
}

function dataOfKind(result: ChartResult | undefined, kind: string): unknown {
  return result?.kind === kind ? result.data : null;
}

/**
 * The real data behind the active chart. Histogram and correlation are handled
 * elsewhere (HistogramChart's fetch mode, the `statistics` prop), so this only
 * drives boxplot, scatter and line.
 *
 * The result is keyed on the active chart, so an in-flight refetch or a failed
 * request can never surface the previous selection's data.
 */
export function useChartData(request: ChartRequest) {
  const { activeChart, datasetId, selectedColumns, filters, columns, refreshKey } = request;
  const { data, loading, error } = useAsyncData(
    () => loadChart(request),
    [activeChart, datasetId, selectedColumns, filters, columns, refreshKey],
    { enabled: fetchEnabled(request), errorMessage: 'Failed to load chart data' },
  );
  return {
    loading,
    error,
    boxplotData: dataOfKind(data, 'boxplot') as BoxPlotData | null,
    scatterData: dataOfKind(data, 'scatter') as ScatterPlotData | null,
    lineData: dataOfKind(data, 'line') as LineChartData | null,
  };
}
