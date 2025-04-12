export interface CorrelationMatrix {
  columns: string[];
  matrix: number[][];
}

export interface HistogramData {
  bins: number[];
  binEdges: number[];
  counts: number[];
  min: number;
  max: number;
}

export interface BoxPlotData {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers: number[];
}

export async function getCorrelationMatrix(datasetId: string): Promise<CorrelationMatrix> {
  const response = await fetch(`/api/visualizations/correlation/${datasetId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch correlation matrix');
  }
  return response.json();
}

export async function getHistogram(datasetId: string, column: string, bins: number = 50): Promise<HistogramData> {
  const response = await fetch(`/api/visualizations/histogram/${datasetId}/${column}?bins=${bins}`);
  if (!response.ok) {
    throw new Error('Failed to fetch histogram data');
  }
  return response.json();
}

export async function getBoxPlot(datasetId: string, column: string): Promise<BoxPlotData> {
  const response = await fetch(`/api/visualizations/boxplot/${datasetId}/${column}`);
  if (!response.ok) {
    throw new Error('Failed to fetch boxplot data');
  }
  return response.json();
} 