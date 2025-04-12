import { BoxPlotData } from '@/lib/services/visualization';

interface BoxplotChartProps {
  data: BoxPlotData;
}

export function BoxplotChart({ data }: BoxplotChartProps) {
  const width = 400;
  const height = 200;
  const padding = 40;
  const boxWidth = 60;
  
  // Calculate scales
  const xScale = (width - 2 * padding) / 1;
  const yScale = (height - 2 * padding) / (data.max - data.min);
  
  // Calculate positions
  const getY = (value: number) => height - padding - (value - data.min) * yScale;
  const getX = () => padding + xScale / 2;
  
  // Calculate box positions
  const medianY = getY(data.median);
  const q1Y = getY(data.q1);
  const q3Y = getY(data.q3);
  const minY = getY(data.min);
  const maxY = getY(data.max);
  const x = getX();
  
  return (
    <div className="w-full h-[300px] flex items-center justify-center">
      <svg width={width} height={height}>
        {/* Whiskers */}
        <line
          x1={x}
          y1={minY}
          x2={x}
          y2={maxY}
          stroke="black"
          strokeWidth={1}
        />
        
        {/* Box */}
        <rect
          x={x - boxWidth/2}
          y={q3Y}
          width={boxWidth}
          height={q1Y - q3Y}
          fill="white"
          stroke="black"
          strokeWidth={1}
        />
        
        {/* Median line */}
        <line
          x1={x - boxWidth/2}
          y1={medianY}
          x2={x + boxWidth/2}
          y2={medianY}
          stroke="black"
          strokeWidth={1}
        />
        
        {/* Outliers */}
        {data.outliers.map((outlier, index) => (
          <circle
            key={index}
            cx={x}
            cy={getY(outlier)}
            r={3}
            fill="red"
          />
        ))}
      </svg>
    </div>
  );
} 