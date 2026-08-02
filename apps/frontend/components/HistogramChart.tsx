import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { HistogramData, getHistogram } from '@/lib/services/visualization';
import { getAuthToken } from '@/lib/auth-helpers';

interface HistogramChartProps {
  /** Pre-computed histogram data. Takes precedence over datasetId/column. */
  data?: HistogramData;
  /** Dataset to fetch histogram data from when `data` is not supplied. */
  datasetId?: string;
  /** Column to fetch histogram data for when `data` is not supplied. */
  column?: string;
  /** Number of bins to request when fetching by datasetId/column. */
  bins?: number;
  /** Chart height in pixels. */
  height?: number;
}

export function HistogramChart({ data, datasetId, column, bins = 50, height = 300 }: HistogramChartProps) {

  const { data: fetched, error } = useAsyncData(
    async () => {
      // The histogram route requires auth (get_current_user_id) — resolve and
      // forward the bearer token or every request 401s.
      const token = await getAuthToken();
      return getHistogram(datasetId!, column!, bins, token ?? undefined);
    },
    [datasetId, column, bins],
    { enabled: !data && !!datasetId && !!column },
  );

  // A supplied `data` prop always wins; only then does the fetch matter.
  const fetchedData = data ?? fetched ?? null;
  // A failed request must stay distinguishable from a column with no data.
  const fetchError = !data && error !== null;

  if (fetchError) {
    return (
      <div className="flex items-center justify-center text-sm text-destructive" style={{ height }}>
        Failed to load histogram data
      </div>
    );
  }

  if (!fetchedData) {
    return (
      <div className="flex items-center justify-center text-sm text-muted-foreground" style={{ height }}>
        No histogram data available
      </div>
    );
  }

  // binEdges should have bins.length + 1 entries; guard against a malformed
  // payload so a short edges array degrades the label instead of crashing.
  const chartData = fetchedData.bins.map((count, index) => ({
    bin: `${fetchedData.binEdges[index]?.toFixed(2) ?? '?'} - ${fetchedData.binEdges[index + 1]?.toFixed(2) ?? '?'}`,
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
