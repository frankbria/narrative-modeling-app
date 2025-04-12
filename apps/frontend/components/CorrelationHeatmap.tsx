import { useMemo, useRef, useEffect, useState } from 'react';
import { StatItem } from '@/lib/utils';
import { CorrelationMatrix } from '@/lib/services/visualization';

interface CorrelationHeatmapProps {
  stats: StatItem[];
}

export function CorrelationHeatmap({ stats }: CorrelationHeatmapProps) {
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
    console.log('Rendering CorrelationHeatmap with stats:', stats);
    
    if (!Array.isArray(stats)) {
      console.error('Stats is not an array:', stats);
      return null;
    }

    // Filter for numeric columns - only check field_type
    const numericStats = stats.filter(stat => stat.field_type === 'numeric');
    
    console.log('Found numeric stats:', numericStats.length);
    console.log('Numeric stats:', numericStats);

    if (numericStats.length < 2) {
      console.log('Not enough numeric columns for correlation matrix');
      return null;
    }

    // Create correlation matrix
    const matrix: number[][] = [];
    const columns = numericStats.map(stat => stat.field_name);

    // Initialize matrix with 1s on diagonal
    for (let i = 0; i < numericStats.length; i++) {
      matrix[i] = new Array(numericStats.length).fill(0);
      matrix[i][i] = 1;
    }

    // Calculate correlations
    for (let i = 0; i < numericStats.length; i++) {
      for (let j = i + 1; j < numericStats.length; j++) {
        // Generate a random correlation between -1 and 1 for demonstration
        // In a real app, you would calculate this based on actual data
        const correlation = Math.random() * 2 - 1;
        
        matrix[i][j] = correlation;
        matrix[j][i] = correlation;
      }
    }

    console.log('Created correlation matrix:', { columns, matrix });
    return { columns, matrix } as CorrelationMatrix;
  }, [stats]);

  if (!correlationMatrix) {
    return (
      <div className="text-center p-4 text-gray-500">
        Not enough numeric columns to generate correlation matrix.
        Found {stats.filter(s => s.field_type === 'numeric').length} numeric columns.
      </div>
    );
  }

  const getColor = (value: number) => {
    const absValue = Math.abs(value);
    const hue = value > 0 ? 120 : 0; // Green for positive, Red for negative
    return `hsl(${hue}, 70%, ${50 + absValue * 25}%)`;
  };

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
      <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`}>
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
                    fill: Math.abs(value) > 0.5 ? 'white' : 'black',
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
    </div>
  );
} 