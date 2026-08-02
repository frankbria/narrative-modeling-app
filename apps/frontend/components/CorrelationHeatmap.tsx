import { useMemo, useRef, useEffect, useState } from 'react';
import { StatItem } from '@/lib/utils';
import { CorrelationMatrix } from '@/lib/services/visualization';

interface CorrelationHeatmapProps {
  stats: StatItem[];
  /** Backend-computed correlation matrix (statistics.correlation_matrix).
   *  Without it the heatmap renders an empty state — it never synthesizes values. */
  correlationMatrix?: Record<string, Record<string, number>> | null;
}

export function CorrelationHeatmap({ stats, correlationMatrix: matrixProp }: CorrelationHeatmapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  
  // Update dimensions when container size changes
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    
    return () => {
      window.removeEventListener('resize', updateDimensions);
    };
  }, []);

  const correlationMatrix = useMemo(() => {
    // Only the backend-computed matrix is rendered; with none available the
    // heatmap shows the empty state rather than fabricated coefficients.
    if (!matrixProp) {
      return null;
    }

    const columns = Object.keys(matrixProp);
    if (columns.length < 2) {
      return null;
    }

    const matrix = columns.map((row) =>
      columns.map(
        // Mirror the symmetric entry before defaulting, so a triangle-only
        // payload doesn't render missing cells as zero correlation.
        (col) => matrixProp[row]?.[col] ?? matrixProp[col]?.[row] ?? (row === col ? 1 : 0)
      )
    );

    return { columns, matrix } as CorrelationMatrix;
  }, [matrixProp]);

  if (!correlationMatrix) {
    return (
      <div className="text-center p-4 text-muted-foreground">
        Not enough numeric columns to generate correlation matrix.
        Found {stats.filter(s => s.field_type === 'numeric').length} numeric columns.
      </div>
    );
  }

  // Diverging blue↔white↔red scale (issue #282): red/green is the worst pairing
  // for red-green colour-vision deficiency, whereas blue-vs-red stays
  // distinguishable across the common CVD types. White == no correlation.
  const cellHsl = (value: number) => {
    const absValue = Math.min(Math.abs(value), 1);
    const hue = value >= 0 ? 0 : 220; // red for positive, blue for negative
    const lightness = 100 - absValue * 55; // 100% (white, at 0) → 45% (strong)
    return { hue, saturation: 65, lightness };
  };
  const getColor = (value: number) => {
    const { hue, saturation, lightness } = cellHsl(value);
    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  };

  // WCAG 1.4.3: pick black/white cell-label text by actual relative luminance,
  // not a fixed correlation cutoff — otherwise white-on-colour dips below the
  // 4.5:1 AA minimum in a narrow magnitude band (~0.78–0.83). Blue is darker
  // than red at equal magnitude, so a value-only threshold can't serve both.
  const relativeLuminance = (h: number, s: number, l: number) => {
    s /= 100;
    l /= 100;
    const k = (n: number) => (n + h / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const ch = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
    const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    return 0.2126 * lin(ch(0)) + 0.7152 * lin(ch(8)) + 0.0722 * lin(ch(4));
  };
  const textColor = (value: number) => {
    const { hue, saturation, lightness } = cellHsl(value);
    const L = relativeLuminance(hue, saturation, lightness);
    const contrastWhite = 1.05 / (L + 0.05);
    const contrastBlack = (L + 0.05) / 0.05;
    return contrastWhite >= contrastBlack ? 'white' : 'black';
  };

  // A screen-reader summary naming the strongest off-diagonal correlation.
  const cols = correlationMatrix.columns;
  let strongest = { a: '', b: '', v: 0 };
  correlationMatrix.matrix.forEach((row, i) =>
    row.forEach((v, j) => {
      if (i < j && Math.abs(v) > Math.abs(strongest.v)) {
        strongest = { a: cols[i], b: cols[j], v };
      }
    })
  );
  const ariaSummary =
    `Correlation heatmap of ${cols.length} numeric columns. Cells range from ` +
    `strong negative (blue) through none (white) to strong positive (red).` +
    (strongest.a
      ? ` Strongest correlation: ${strongest.a} and ${strongest.b} at ${strongest.v.toFixed(2)}.`
      : '');

  // Calculate dimensions based on container size and number of columns
  const numColumns = correlationMatrix.columns.length;
  
  // Ensure minimum sizes for readability
  const minCellSize = 60; // Minimum cell size for readability
  const minLabelHeight = 80; // Minimum space for labels
  const minLabelWidth = 100; // Minimum space for labels
  const minPadding = 20; // Minimum padding
  
  // Calculate available space
  const availableWidth = Math.max(dimensions.width, minCellSize * numColumns + minLabelWidth + minPadding * 2);
  const availableHeight = Math.max(dimensions.height, minCellSize * numColumns + minLabelHeight + minPadding * 2);
  
  // Calculate cell size to fit within container while maintaining readability
  const cellSize = Math.max(
    minCellSize,
    Math.min(
      (availableWidth - minLabelWidth - minPadding * 2) / numColumns,
      (availableHeight - minLabelHeight - minPadding * 2) / numColumns
    )
  );
  
  // Calculate label areas and padding
  const labelHeight = Math.max(minLabelHeight, availableHeight * 0.15);
  const labelWidth = Math.max(minLabelWidth, availableWidth * 0.15);
  const padding = Math.max(minPadding, Math.min(availableWidth, availableHeight) * 0.05);
  
  // Calculate total dimensions
  const width = numColumns * cellSize + labelWidth + padding * 2;
  const height = numColumns * cellSize + labelHeight + padding * 2;

  return (
    <div ref={containerRef} className="w-full h-[400px]">
      <svg
        width="100%"
        height="calc(100% - 2rem)"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaSummary}
      >
        <title>{ariaSummary}</title>
        <g transform={`translate(${labelWidth + padding}, ${labelHeight + padding})`}>
          {/* Column headers */}
          {correlationMatrix.columns.map((col, i) => (
            <g key={`col-${col}`} transform={`translate(${i * cellSize + cellSize/2}, -${labelHeight/2})`}>
              <text
                x="0"
                y="0"
                textAnchor="middle"
                transform="rotate(-45)"
                className="text-xs font-medium"
                style={{ fontSize: Math.max(10, cellSize * 0.12) + 'px' }}
              >
                {col}
              </text>
            </g>
          ))}
          
          {/* Row headers */}
          {correlationMatrix.columns.map((col, i) => (
            <g key={`row-${col}`} transform={`translate(-${labelWidth/2}, ${i * cellSize + cellSize/2})`}>
              <text
                x="0"
                y="0"
                textAnchor="end"
                className="text-xs font-medium"
                style={{ fontSize: Math.max(10, cellSize * 0.12) + 'px' }}
              >
                {col}
              </text>
            </g>
          ))}
          
          {/* Correlation cells */}
          {correlationMatrix.matrix.map((row, i) =>
            row.map((value, j) => (
              <g key={`cell-${i}-${j}`}>
                <rect
                  x={j * cellSize}
                  y={i * cellSize}
                  width={cellSize}
                  height={cellSize}
                  fill={getColor(value)}
                  stroke="white"
                  strokeWidth="1"
                />
                <text
                  x={j * cellSize + cellSize/2}
                  y={i * cellSize + cellSize/2}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="text-xs"
                  style={{
                    fontSize: Math.max(8, cellSize * 0.1) + 'px',
                    fill: textColor(value),
                    fontWeight: Math.abs(value) > 0.7 ? 'bold' : 'normal'
                  }}
                >
                  {value.toFixed(2)}
                </text>
              </g>
            ))
          )}
        </g>
      </svg>

      {/* Colour legend so the diverging scale is decodable without reading cells */}
      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground" aria-hidden="true">
        <span>-1</span>
        <div
          className="h-2 flex-1 rounded"
          style={{
            background: `linear-gradient(to right, ${getColor(-1)}, ${getColor(0)}, ${getColor(1)})`,
          }}
        />
        <span>+1</span>
        <span className="ml-1 whitespace-nowrap">(blue = negative, red = positive)</span>
      </div>
    </div>
  );
} 