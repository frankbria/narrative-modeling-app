import React, { useMemo, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatItem } from '@/lib/utils';

interface CorrelationHeatmapProps {
  stats: StatItem[];
  className?: string;
}

export function CorrelationHeatmap({ stats, className }: CorrelationHeatmapProps) {
  // Helper function to calculate a simplified correlation
  // In a real app, you would use the actual data to calculate Pearson correlation
  const calculateCorrelation = (stat1: StatItem, stat2: StatItem): number => {
    // Check if numeric_stats exists, if not, create a default one
    const stats1 = stat1.numeric_stats || {
      min: 0,
      max: 100,
      mean: 50,
      median: 50,
      mode: 50,
      std_dev: 25
    };
    
    const stats2 = stat2.numeric_stats || {
      min: 0,
      max: 100,
      mean: 50,
      median: 50,
      mode: 50,
      std_dev: 25
    };
    
    // Log if we're using default stats
    if (!stat1.numeric_stats || !stat2.numeric_stats) {
      console.log('Using default numeric_stats for correlation calculation', { 
        stat1: stat1.field_name, 
        stat2: stat2.field_name,
        hasStats1: !!stat1.numeric_stats,
        hasStats2: !!stat2.numeric_stats
      });
    }
    
    // This is a simplified correlation calculation for demo purposes
    // In a real app, you would use the actual data to calculate Pearson correlation
    const std1 = stats1.std_dev;
    const std2 = stats2.std_dev;
    
    // Generate a random correlation between -1 and 1
    // In a real app, you would calculate this from the actual data
    const randomCorrelation = Math.random() * 2 - 1;
    
    // Scale the correlation based on the standard deviations
    const scaledCorrelation = randomCorrelation * (std1 / std2);
    
    // Clamp to [-1, 1]
    return Math.max(-1, Math.min(1, scaledCorrelation));
  };

  // Debug logging
  useEffect(() => {
    console.log('CorrelationHeatmap rendered with stats:', stats);
    console.log('Stats length:', stats?.length);
    console.log('Stats structure:', JSON.stringify(stats, null, 2));
    
    // Check if stats is undefined or null
    if (!stats) {
      console.error('CorrelationHeatmap: stats is undefined or null');
    }
    
    // Check if stats is an array
    if (stats && !Array.isArray(stats)) {
      console.error('CorrelationHeatmap: stats is not an array', stats);
    }
  }, [stats]);

  // Filter for numeric columns only
  const numericStats = useMemo(() => {
    if (!stats || !Array.isArray(stats)) {
      console.error('CorrelationHeatmap: stats is not an array', stats);
      return [];
    }
    
    const filtered = stats.filter(stat => {
      if (!stat) {
        console.error('CorrelationHeatmap: stat is undefined or null');
        return false;
      }
      
      if (!stat.field_type) {
        console.error('CorrelationHeatmap: stat.field_type is undefined or null', stat);
        return false;
      }
      
      // Check if the field is numeric
      const isNumeric = stat.field_type === 'numeric';
      
      if (!isNumeric) {
        console.log(`Skipping non-numeric field: ${stat.field_name}, type: ${stat.field_type}`);
      } else {
        console.log(`Found numeric field: ${stat.field_name}`, {
          hasNumericStats: !!stat.numeric_stats,
          fieldType: stat.field_type
        });
      }
      
      return isNumeric;
    });
    
    console.log('Numeric stats count:', filtered.length);
    console.log('Numeric stats:', filtered.map(stat => ({
      field_name: stat.field_name,
      field_type: stat.field_type,
      hasNumericStats: !!stat.numeric_stats
    })));
    return filtered;
  }, [stats]);

  // Calculate correlation matrix
  const correlationMatrix = useMemo(() => {
    if (numericStats.length < 2) {
      console.log('Not enough numeric columns for correlation matrix:', numericStats.length);
      return null;
    }

    // Create a matrix of correlations
    const matrix: number[][] = [];
    const labels: string[] = [];

    // Initialize matrix with 1s on diagonal
    for (let i = 0; i < numericStats.length; i++) {
      matrix[i] = new Array(numericStats.length).fill(0);
      matrix[i][i] = 1; // Perfect correlation with itself
      labels.push(numericStats[i].field_name);
    }

    // Calculate correlations between each pair of columns
    for (let i = 0; i < numericStats.length; i++) {
      for (let j = i + 1; j < numericStats.length; j++) {
        // For demo purposes, we'll use a simplified correlation calculation
        // In a real app, you would use the actual data to calculate Pearson correlation
        const correlation = calculateCorrelation(numericStats[i], numericStats[j]);
        matrix[i][j] = correlation;
        matrix[j][i] = correlation; // Correlation matrix is symmetric
      }
    }

    console.log('Correlation matrix created with labels:', labels);
    return { matrix, labels };
  }, [numericStats]);

  // Generate color based on correlation value
  const getColor = (value: number): string => {
    // Red for negative correlations, blue for positive
    const r = value < 0 ? Math.abs(value) * 255 : 0;
    const b = value > 0 ? value * 255 : 0;
    const g = 0;
    const a = Math.abs(value) * 0.7 + 0.3; // Opacity based on correlation strength
    
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  };

  if (!correlationMatrix || numericStats.length < 2) {
    console.log('Rendering fallback UI due to insufficient numeric columns');
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Correlation Heatmap</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">
            Not enough numeric columns to generate a correlation matrix. 
            Found {numericStats.length} numeric columns, need at least 2.
          </p>
          {stats && stats.length > 0 && (
            <div className="mt-2 text-xs text-gray-400">
              <p>Available columns:</p>
              <ul className="list-disc pl-4 mt-1">
                {stats.map((stat, index) => (
                  <li key={index}>
                    {stat.field_name} ({stat.field_type})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Correlation Heatmap</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <div className="min-w-[500px]">
            <div className="grid grid-cols-[auto_repeat(auto-fit,minmax(40px,1fr))] gap-1">
              {/* Header row */}
              <div className="p-2 font-bold text-center bg-gray-100"></div>
              {correlationMatrix.labels.map((label, i) => (
                <div key={i} className="p-2 font-bold text-center bg-gray-100 text-xs rotate-45 origin-bottom-left whitespace-nowrap">
                  {label}
                </div>
              ))}
              
              {/* Matrix rows */}
              {correlationMatrix.matrix.map((row, i) => (
                <React.Fragment key={i}>
                  {/* Row label */}
                  <div className="p-2 font-bold text-center bg-gray-100 text-xs">
                    {correlationMatrix.labels[i]}
                  </div>
                  
                  {/* Correlation values */}
                  {row.map((value, j) => (
                    <div 
                      key={j} 
                      className="p-2 text-center text-xs"
                      style={{ 
                        backgroundColor: getColor(value),
                        color: Math.abs(value) > 0.5 ? 'white' : 'black'
                      }}
                    >
                      {value.toFixed(2)}
                    </div>
                  ))}
                </React.Fragment>
              ))}
            </div>
            
            {/* Legend */}
            <div className="mt-4 flex items-center justify-center space-x-4">
              <div className="flex items-center">
                <div className="w-4 h-4 bg-red-500 mr-1"></div>
                <span className="text-xs">Negative Correlation</span>
              </div>
              <div className="flex items-center">
                <div className="w-4 h-4 bg-blue-500 mr-1"></div>
                <span className="text-xs">Positive Correlation</span>
              </div>
              <div className="flex items-center">
                <div className="w-4 h-4 bg-gray-200 mr-1"></div>
                <span className="text-xs">No Correlation</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
} 