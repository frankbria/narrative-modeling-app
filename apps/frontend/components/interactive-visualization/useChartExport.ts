import { useState } from 'react';
import { getHistogram } from '@/lib/services/visualization';
import type { DatasetStatistics } from '@/lib/types/api';
import type { FetchedChart } from './chartSelection';
import { authToken } from './useChartData';

export interface ExportSources {
  activeChart: string;
  datasetId: string;
  statistics?: DatasetStatistics;
  numericSelected: string[];
  binCount: number;
  /** What the fetched charts currently hold. */
  fetched: Record<FetchedChart, unknown>;
}

async function histogramPayload(sources: ExportSources): Promise<unknown> {
  const { datasetId, numericSelected, binCount } = sources;
  if (!datasetId || numericSelected.length === 0) return null;
  return getHistogram(datasetId, numericSelected[0], binCount, await authToken());
}

type PayloadBuilder = (sources: ExportSources) => unknown;

// Histogram fetches itself inside HistogramChart, so its export re-fetches the
// selected column's data on demand.
const PAYLOADS = new Map<string, PayloadBuilder>([
  ['correlation', sources => sources.statistics?.correlation_matrix ?? null],
  ['histogram', histogramPayload],
  ['boxplot', sources => sources.fetched.boxplot],
  ['scatter', sources => sources.fetched.scatter],
  ['line', sources => sources.fetched.line],
]);

async function exportPayload(sources: ExportSources): Promise<unknown> {
  const build = PAYLOADS.get(sources.activeChart);
  return build ? build(sources) : null;
}

function downloadJson(payload: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Downloads the data behind the active chart as JSON. Export failures are the
 * user's action, not the chart load's, so they are kept apart from its error.
 */
export function useChartExport(sources: ExportSources) {
  const [exportError, setExportError] = useState<string | null>(null);

  const exportChart = async () => {
    try {
      const payload = await exportPayload(sources);
      if (payload == null) {
        setExportError('No chart data available to export yet');
        return;
      }
      downloadJson(payload, `${sources.activeChart}_${sources.datasetId}.json`);
    } catch (err) {
      console.error('Export failed:', err);
      setExportError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  const clearExportError = () => setExportError(null);

  return { exportError, exportChart, clearExportError };
}
