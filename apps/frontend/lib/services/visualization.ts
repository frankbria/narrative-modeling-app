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

export interface ScatterPlotData {
  data: Array<{
    x: number;
    y: number;
    label?: string;
    category?: string;
  }>;
  xLabel: string;
  yLabel: string;
  title?: string;
  correlation?: number;
}

export interface LineChartData {
  data: Array<{
    x: string | number;
    [key: string]: string | number;
  }>;
  lines: Array<{
    dataKey: string;
    label: string;
    color?: string;
  }>;
  xLabel: string;
  yLabel: string;
  title?: string;
  showBrush?: boolean;
}

export interface TimeSeriesData {
  timestamps: string[];
  values: number[];
  label: string;
}

export interface ChartFilter {
  column: string;
  operator: 'equals' | 'greater_than' | 'less_than' | 'contains' | 'between';
  value: string | number | [number, number];
}

export async function getCorrelationMatrix(datasetId: string, token?: string): Promise<CorrelationMatrix> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const response = await fetch(`${apiUrl}/api/v1/visualizations/correlation/${datasetId}`, {
    headers
  });
  if (!response.ok) {
    throw new Error('Failed to fetch correlation matrix');
  }
  return response.json();
}

export async function getHistogram(datasetId: string, column: string, bins: number = 50, token?: string): Promise<HistogramData> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const response = await fetch(`${apiUrl}/api/v1/visualizations/histogram/${datasetId}/${column}?bins=${bins}`, {
    headers
  });
  if (!response.ok) {
    throw new Error('Failed to fetch histogram data');
  }
  return response.json();
}

export async function getBoxPlot(datasetId: string, column: string, token?: string): Promise<BoxPlotData> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const response = await fetch(`${apiUrl}/api/v1/visualizations/boxplot/${datasetId}/${column}`, {
    headers
  });
  if (!response.ok) {
    throw new Error('Failed to fetch boxplot data');
  }
  return response.json();
}

export async function getScatterPlot(
  datasetId: string, 
  xColumn: string, 
  yColumn: string,
  filters?: ChartFilter[],
  token?: string
): Promise<ScatterPlotData> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const queryParams = new URLSearchParams()
  if (filters && filters.length > 0) {
    queryParams.append('filters', JSON.stringify(filters))
  }
  
  const response = await fetch(
    `${apiUrl}/api/v1/visualizations/scatter/${datasetId}/${xColumn}/${yColumn}?${queryParams}`,
    { headers }
  );
  if (!response.ok) {
    throw new Error('Failed to fetch scatter plot data');
  }
  return response.json();
}

export async function getLineChart(
  datasetId: string, 
  xColumn: string, 
  yColumns: string[],
  filters?: ChartFilter[],
  token?: string
): Promise<LineChartData> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const queryParams = new URLSearchParams()
  queryParams.append('y_columns', yColumns.join(','))
  if (filters && filters.length > 0) {
    queryParams.append('filters', JSON.stringify(filters))
  }
  
  const response = await fetch(
    `${apiUrl}/api/v1/visualizations/line/${datasetId}/${xColumn}?${queryParams}`,
    { headers }
  );
  if (!response.ok) {
    throw new Error('Failed to fetch line chart data');
  }
  return response.json();
}

export async function getTimeSeries(
  datasetId: string, 
  timeColumn: string, 
  valueColumn: string,
  filters?: ChartFilter[],
  token?: string
): Promise<TimeSeriesData> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const queryParams = new URLSearchParams()
  if (filters && filters.length > 0) {
    queryParams.append('filters', JSON.stringify(filters))
  }
  
  const response = await fetch(
    `${apiUrl}/api/v1/visualizations/timeseries/${datasetId}/${timeColumn}/${valueColumn}?${queryParams}`,
    { headers }
  );
  if (!response.ok) {
    throw new Error('Failed to fetch time series data');
  }
  return response.json();
}

export async function getFilteredData(
  datasetId: string,
  filters: ChartFilter[],
  columns?: string[],
  token?: string
): Promise<any[]> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  const queryParams = new URLSearchParams()
  queryParams.append('filters', JSON.stringify(filters))
  if (columns && columns.length > 0) {
    queryParams.append('columns', columns.join(','))
  }
  
  const response = await fetch(
    `${apiUrl}/api/v1/visualizations/filtered/${datasetId}?${queryParams}`,
    { headers }
  );
  if (!response.ok) {
    throw new Error('Failed to fetch filtered data');
  }
  return response.json();
} 