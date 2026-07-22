import { BoxPlotData } from '@/lib/services/visualization';

interface BoxplotChartProps {
  data: BoxPlotData;
}

/**
 * Box-and-whisker plot (issue #79) with accessibility hardening (issue #282):
 * responsive viewBox, a labeled y-axis with the five-number summary, a
 * `role="img"` text summary for screen readers, and outliers drawn as hollow
 * rings (shape, not colour alone) so they read without relying on red.
 */
export function BoxplotChart({ data }: BoxplotChartProps) {
  const width = 460;
  const height = 220;
  const padding = 40;
  const boxWidth = 60;

  // Guard a degenerate range (all values equal) so we never divide by zero.
  const range = data.max - data.min || 1;
  const yScale = (height - 2 * padding) / range;

  const getY = (value: number) => height - padding - (value - data.min) * yScale;
  const x = padding + (width - 2 * padding) / 2;

  const medianY = getY(data.median);
  const q1Y = getY(data.q1);
  const q3Y = getY(data.q3);
  const minY = getY(data.min);
  const maxY = getY(data.max);

  const fmt = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(2));

  // Axis ticks = the five-number summary (deduped, sorted top-to-bottom).
  const ticks = Array.from(new Set([data.max, data.q3, data.median, data.q1, data.min])).sort(
    (a, b) => b - a
  );

  const summary =
    `Box plot. Minimum ${fmt(data.min)}, first quartile ${fmt(data.q1)}, ` +
    `median ${fmt(data.median)}, third quartile ${fmt(data.q3)}, maximum ${fmt(data.max)}. ` +
    `${data.outliers.length} outlier${data.outliers.length === 1 ? '' : 's'}.`;

  return (
    <div className="w-full h-[300px] flex items-center justify-center">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={summary}
        className="max-w-[520px]"
      >
        <title>{summary}</title>

        {/* Y axis with five-number ticks + value labels */}
        <line
          x1={padding}
          y1={getY(data.max)}
          x2={padding}
          y2={getY(data.min)}
          stroke="#9CA3AF"
          strokeWidth={1}
        />
        {ticks.map((value) => (
          <g key={`tick-${value}`}>
            <line
              x1={padding - 4}
              y1={getY(value)}
              x2={padding}
              y2={getY(value)}
              stroke="#9CA3AF"
              strokeWidth={1}
            />
            <text
              x={padding - 8}
              y={getY(value)}
              textAnchor="end"
              dominantBaseline="middle"
              className="fill-gray-600"
              style={{ fontSize: '10px' }}
            >
              {fmt(value)}
            </text>
          </g>
        ))}

        {/* Whiskers */}
        <line x1={x} y1={minY} x2={x} y2={maxY} stroke="#111827" strokeWidth={1} />
        {/* Whisker caps */}
        <line x1={x - boxWidth / 4} y1={maxY} x2={x + boxWidth / 4} y2={maxY} stroke="#111827" strokeWidth={1} />
        <line x1={x - boxWidth / 4} y1={minY} x2={x + boxWidth / 4} y2={minY} stroke="#111827" strokeWidth={1} />

        {/* Box (Q1–Q3) */}
        <rect
          x={x - boxWidth / 2}
          y={q3Y}
          width={boxWidth}
          height={q1Y - q3Y}
          fill="#DBEAFE"
          stroke="#1D4ED8"
          strokeWidth={1}
        />

        {/* Median line */}
        <line
          x1={x - boxWidth / 2}
          y1={medianY}
          x2={x + boxWidth / 2}
          y2={medianY}
          stroke="#1D4ED8"
          strokeWidth={2}
        />

        {/* Outliers — hollow rings so they read by shape, not colour alone */}
        {data.outliers.map((outlier, index) => (
          <circle
            key={index}
            cx={x}
            cy={getY(outlier)}
            r={4}
            fill="none"
            stroke="#DC2626"
            strokeWidth={1.5}
          />
        ))}
      </svg>
    </div>
  );
}
