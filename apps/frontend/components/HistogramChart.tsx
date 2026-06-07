import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { HistogramData, getHistogram } from '@/lib/services/visualization';

interface HistogramChartProps {
  /** Pre-computed histogram data. Takes precedence over datasetId/column. */
  data?: HistogramData;
  /** Dataset to fetch histogram data from when `data` is not supplied. */
  datasetId?: string;
  /** Column to fetch histogram data for when `data` is not supplied. */
  column?: string;
  /** Chart height in pixels. */
  height?: number;
}

export function HistogramChart({ data, datasetId, column, height = 300 }: HistogramChartProps) {
  const [fetchedData, setFetchedData] = useState<HistogramData | null>(data ?? null);

  useEffect(() => {
    if (data) {
      setFetchedData(data);
      return;
    }

    if (datasetId && column) {
      let cancelled = false;
      getHistogram(datasetId, column)
        .then((result) => {
          if (!cancelled) setFetchedData(result);
        })
        .catch(() => {
          if (!cancelled) setFetchedData(null);
        });
      return () => {
        cancelled = true;
      };
    }
  }, [data, datasetId, column]);

  if (!fetchedData) {
    return (
      <div className="flex items-center justify-center text-sm text-muted-foreground" style={{ height }}>
        No histogram data available
      </div>
    );
  }

  const chartData = fetchedData.bins.map((count, index) => ({
    bin: `${fetchedData.binEdges[index].toFixed(2)} - ${fetchedData.binEdges[index + 1].toFixed(2)}`,
    count
  }));

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="bin" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" fill="#8884d8" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
