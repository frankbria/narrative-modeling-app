import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { HistogramData } from '@/lib/services/visualization';

interface HistogramChartProps {
  data: HistogramData;
}

export function HistogramChart({ data }: HistogramChartProps) {
  const chartData = data.bins.map((count, index) => ({
    bin: `${data.binEdges[index].toFixed(2)} - ${data.binEdges[index + 1].toFixed(2)}`,
    count
  }));

  return (
    <div className="w-full h-[300px]">
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