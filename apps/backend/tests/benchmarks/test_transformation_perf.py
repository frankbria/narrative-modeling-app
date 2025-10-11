"""
Transformation performance benchmarks.

Tests transformation operations to ensure they meet performance targets:
- Preview generation: <2s for 10K rows
- Transformation application: <30s for 100K rows
"""
import pytest
import pandas as pd
from app.services.transformation_service.transformation_engine import (
    TransformationEngine,
    TransformationType,
)


class TestTransformationPerformance:
    """Benchmark transformation operations"""

    def test_preview_remove_duplicates_10k(self, benchmark, benchmark_data_10k, performance_targets):
        """Benchmark preview generation for remove_duplicates (10K rows)"""
        engine = TransformationEngine()

        def run_preview():
            return engine.preview_transformation(
                df=benchmark_data_10k,
                transformation_type=TransformationType.REMOVE_DUPLICATES,
                parameters={'keep': 'first'},
                n_rows=100
            )

        result = benchmark(run_preview)

        # Verify result
        assert result.success
        # Check performance target
        assert benchmark.stats['mean'] < performance_targets['transformation_preview_10k'], \
            f"Preview took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_preview_10k']}s"

    def test_preview_fill_missing_10k(self, benchmark, benchmark_data_10k, performance_targets):
        """Benchmark preview generation for fill_missing (10K rows)"""
        engine = TransformationEngine()

        def run_preview():
            return engine.preview_transformation(
                df=benchmark_data_10k,
                transformation_type=TransformationType.FILL_MISSING,
                parameters={'columns': ['with_missing'], 'method': 'mean'},
                n_rows=100
            )

        result = benchmark(run_preview)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_preview_10k'], \
            f"Preview took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_preview_10k']}s"

    def test_preview_drop_missing_10k(self, benchmark, benchmark_data_10k, performance_targets):
        """Benchmark preview generation for drop_missing (10K rows)"""
        engine = TransformationEngine()

        def run_preview():
            return engine.preview_transformation(
                df=benchmark_data_10k,
                transformation_type=TransformationType.DROP_MISSING,
                parameters={'how': 'any'},
                n_rows=100
            )

        result = benchmark(run_preview)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_preview_10k'], \
            f"Preview took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_preview_10k']}s"

    def test_preview_trim_whitespace_10k(self, benchmark, benchmark_data_10k, performance_targets):
        """Benchmark preview generation for trim_whitespace (10K rows)"""
        engine = TransformationEngine()

        def run_preview():
            return engine.preview_transformation(
                df=benchmark_data_10k,
                transformation_type=TransformationType.TRIM_WHITESPACE,
                parameters={'columns': ['text']},
                n_rows=100
            )

        result = benchmark(run_preview)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_preview_10k'], \
            f"Preview took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_preview_10k']}s"

    def test_apply_remove_duplicates_100k(self, benchmark, benchmark_data_100k, performance_targets):
        """Benchmark transformation application for remove_duplicates (100K rows)"""
        engine = TransformationEngine()

        def run_apply():
            return engine.apply_transformation(
                df=benchmark_data_100k.copy(),  # Copy to avoid mutation
                transformation_type=TransformationType.REMOVE_DUPLICATES,
                parameters={'keep': 'first'}
            )

        result = benchmark(run_apply)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_apply_100k'], \
            f"Apply took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_apply_100k']}s"

    def test_apply_fill_missing_100k(self, benchmark, benchmark_data_100k, performance_targets):
        """Benchmark transformation application for fill_missing (100K rows)"""
        engine = TransformationEngine()

        def run_apply():
            return engine.apply_transformation(
                df=benchmark_data_100k.copy(),
                transformation_type=TransformationType.FILL_MISSING,
                parameters={'columns': ['with_missing'], 'method': 'mean'}
            )

        result = benchmark(run_apply)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_apply_100k'], \
            f"Apply took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_apply_100k']}s"

    def test_apply_drop_missing_100k(self, benchmark, benchmark_data_100k, performance_targets):
        """Benchmark transformation application for drop_missing (100K rows)"""
        engine = TransformationEngine()

        # Create a dataset with fewer missing values to avoid hitting the 50% data loss threshold
        df = benchmark_data_100k.copy()
        df['with_missing'] = [np.nan if i % 100 == 0 else i for i in range(len(df))]  # Only 1% missing

        def run_apply():
            return engine.apply_transformation(
                df=df.copy(),
                transformation_type=TransformationType.DROP_MISSING,
                parameters={'columns': ['with_missing'], 'how': 'any'}
            )

        result = benchmark(run_apply)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_apply_100k'], \
            f"Apply took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_apply_100k']}s"

    def test_apply_trim_whitespace_100k(self, benchmark, benchmark_data_100k, performance_targets):
        """Benchmark transformation application for trim_whitespace (100K rows)"""
        engine = TransformationEngine()

        def run_apply():
            return engine.apply_transformation(
                df=benchmark_data_100k.copy(),
                transformation_type=TransformationType.TRIM_WHITESPACE,
                parameters={'columns': ['text']}
            )

        result = benchmark(run_apply)

        assert result.success
        assert benchmark.stats['mean'] < performance_targets['transformation_apply_100k'], \
            f"Apply took {benchmark.stats['mean']:.2f}s, target is {performance_targets['transformation_apply_100k']}s"


class TestTransformationScalability:
    """Test transformation scalability across different data sizes"""

    @pytest.mark.parametrize("size,fixture_name", [
        (1000, "benchmark_data_1k"),
        (10000, "benchmark_data_10k"),
        (100000, "benchmark_data_100k"),
    ])
    def test_scalability_remove_duplicates(self, benchmark, size, fixture_name, request):
        """Test how remove_duplicates scales with data size"""
        data = request.getfixturevalue(fixture_name)
        engine = TransformationEngine()

        def run_apply():
            return engine.apply_transformation(
                df=data.copy(),
                transformation_type=TransformationType.REMOVE_DUPLICATES,
                parameters={'keep': 'first'}
            )

        result = benchmark(run_apply)
        assert result.success

        # Log scaling metrics
        print(f"\nRemove duplicates with {size} rows: {benchmark.stats['mean']:.3f}s")

    @pytest.mark.parametrize("size,fixture_name", [
        (1000, "benchmark_data_1k"),
        (10000, "benchmark_data_10k"),
        (100000, "benchmark_data_100k"),
    ])
    def test_scalability_fill_missing(self, benchmark, size, fixture_name, request):
        """Test how fill_missing scales with data size"""
        data = request.getfixturevalue(fixture_name)
        engine = TransformationEngine()

        def run_apply():
            return engine.apply_transformation(
                df=data.copy(),
                transformation_type=TransformationType.FILL_MISSING,
                parameters={'columns': ['with_missing'], 'method': 'mean'}
            )

        result = benchmark(run_apply)
        assert result.success

        # Log scaling metrics
        print(f"\nFill missing with {size} rows: {benchmark.stats['mean']:.3f}s")


# Import numpy for the drop_missing test
import numpy as np
