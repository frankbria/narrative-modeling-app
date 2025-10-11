"""
Performance benchmarks for critical operations.

This package contains benchmark tests to ensure performance targets are met:
- Transformation preview: <2s for 10K rows
- Transformation application: <30s for 100K rows
- Model training: <5min for 50K rows
- Single prediction: <100ms
- Batch prediction: 1000 rows/sec
"""
