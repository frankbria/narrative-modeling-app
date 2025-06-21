import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
from app.models.visualization_cache import (
    HistogramData,
    BoxplotData,
    CorrelationMatrixData,
)


def generate_histogram(data: pd.Series, num_bins: int = 50) -> HistogramData:
    """Generate histogram data for a numeric column"""
    clean_data = data.dropna()
    
    # Handle empty data
    if len(clean_data) == 0:
        return HistogramData(bins=[], counts=[], bin_edges=[])
    
    counts, bin_edges = np.histogram(clean_data, bins=num_bins)
    bins = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]

    return HistogramData(
        bins=bins, counts=counts.tolist(), bin_edges=bin_edges.tolist()
    )


def generate_boxplot(data: pd.Series) -> BoxplotData:
    """Generate boxplot data for a numeric column"""
    q1 = data.quantile(0.25)
    q3 = data.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = data[(data < lower_bound) | (data > upper_bound)].tolist()

    return BoxplotData(
        min=data.min(),
        q1=q1,
        median=data.median(),
        q3=q3,
        max=data.max(),
        outliers=outliers,
    )


def generate_correlation_matrix(df: pd.DataFrame) -> CorrelationMatrixData:
    """Generate correlation matrix for numeric columns"""
    numeric_df = df.select_dtypes(include=[np.number])
    corr_matrix = numeric_df.corr()

    return CorrelationMatrixData(
        matrix=corr_matrix.values.tolist(), columns=corr_matrix.columns.tolist()
    )
