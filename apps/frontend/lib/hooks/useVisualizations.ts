import { useState, useCallback } from 'react';
import { getHistogram, getBoxPlot, getCorrelationMatrix, HistogramData, BoxPlotData, CorrelationMatrix } from '../services/visualization';

export function useVisualizations(datasetId: string) {
  const [histogramData, setHistogramData] = useState<Record<string, HistogramData>>({});
  const [boxplotData, setBoxplotData] = useState<Record<string, BoxPlotData>>({});
  const [correlationData, setCorrelationData] = useState<CorrelationMatrix | null>(null);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, string>>({});

  const fetchHistogram = useCallback(async (columnName: string, numBins: number = 50) => {
    if (!datasetId) return;
    
    const key = `${columnName}-${numBins}`;
    setLoading(prev => ({ ...prev, [`histogram-${key}`]: true }));
    setError(prev => ({ ...prev, [`histogram-${key}`]: '' }));
    
    try {
      const data = await getHistogram(datasetId, columnName, numBins);
      setHistogramData(prev => ({ ...prev, [key]: data }));
    } catch (err) {
      setError(prev => ({ ...prev, [`histogram-${key}`]: err instanceof Error ? err.message : 'Failed to fetch histogram' }));
    } finally {
      setLoading(prev => ({ ...prev, [`histogram-${key}`]: false }));
    }
  }, [datasetId]);

  const fetchBoxplot = useCallback(async (columnName: string) => {
    if (!datasetId) return;
    
    setLoading(prev => ({ ...prev, [`boxplot-${columnName}`]: true }));
    setError(prev => ({ ...prev, [`boxplot-${columnName}`]: '' }));
    try {
      const data = await getBoxPlot(datasetId, columnName);
      setBoxplotData(prev => ({ ...prev, [columnName]: data }));
    } catch (err) {
      setError(prev => ({ ...prev, [`boxplot-${columnName}`]: err instanceof Error ? err.message : 'Failed to fetch boxplot' }));
    } finally {
      setLoading(prev => ({ ...prev, [`boxplot-${columnName}`]: false }));
    }
  }, [datasetId]);

  const fetchCorrelationMatrix = useCallback(async () => {
    if (!datasetId) return;
    
    setLoading(prev => ({ ...prev, correlation: true }));
    setError(prev => ({ ...prev, correlation: '' }));
    
    try {
      const data = await getCorrelationMatrix(datasetId);
      setCorrelationData(data);
    } catch (err) {
      setError(prev => ({ ...prev, correlation: err instanceof Error ? err.message : 'Failed to fetch correlation matrix' }));
    } finally {
      setLoading(prev => ({ ...prev, correlation: false }));
    }
  }, [datasetId]);

  return {
    histogramData,
    boxplotData,
    correlationData,
    loading,
    error,
    fetchHistogram,
    fetchBoxplot,
    fetchCorrelationMatrix,
  };
} 