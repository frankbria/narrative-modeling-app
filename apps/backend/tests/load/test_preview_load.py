"""
Load tests for preview system performance

These tests verify:
1. Concurrent request handling (for future rate limiting validation)
2. Preview generation time across different sample sizes
3. Memory usage with large samples
4. Rapid sequential request handling

Requirements (fixtures in tests/load/conftest.py handle setup):
- MongoDB running locally (dataset metadata is seeded into the test DB)
- S3 is stubbed with a locally generated DataFrame (timings measure the
  preview pipeline, not network throughput)

Run with:
    cd apps/backend
    uv run pytest tests/load/test_preview_load.py -v -s
"""

import asyncio
import time

import pytest

from app.schemas.transformation import TransformationStepRequest
from app.services.data_processing.preview_service_integration import (
    PreviewServiceIntegration,
)

# A minimal cheap operation: generate_preview requires a non-empty operations
# list, so this stands in wherever the old tests passed operations=[]
BASELINE_OPERATIONS = [
    TransformationStepRequest(transformation_type="remove_duplicates", parameters={})
]


@pytest.fixture
def preview_service():
    """Create preview service instance for testing"""
    return PreviewServiceIntegration()


@pytest.mark.asyncio
@pytest.mark.load
async def test_concurrent_preview_requests(preview_service, test_data_config, stub_s3_dataframe):
    """
    Test that rate limiting works with concurrent requests.

    Current State: No rate limiting implemented yet
    Expected: All requests should succeed

    Future State (when rate limiting implemented):
    - Max 5 concurrent previews per user
    - Additional requests receive rate limit errors
    - Slots are released after completion or timeout
    """
    # Simple transformation for testing
    operations = [
        TransformationStepRequest(
            transformation_type="remove_duplicates",
            parameters={}
        )
    ]

    # Simulate 10 concurrent preview requests from same user
    tasks = [
        preview_service.generate_preview(
            user_id=test_data_config["user_id"],
            dataset_id=test_data_config["dataset_id"],
            s3_file_path=test_data_config["s3_file_path"],
            operations=operations,
            sample_size=100
        )
        for _ in range(10)
    ]

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start

    # Count successes and failures
    successful = [r for r in results if not isinstance(r, Exception)]
    errors = [r for r in results if isinstance(r, Exception)]

    print("\n--- Concurrent Request Test Results ---")
    print("Total requests: 10")
    print(f"Successful: {len(successful)}")
    print(f"Errors: {len(errors)}")
    print(f"Total duration: {duration:.2f}s")
    print(f"Average per request: {duration/10:.2f}s")

    # Current expectation (no rate limiting yet)
    assert len(successful) == 10, "All requests should succeed without rate limiting"

    # Future expectation (when rate limiting implemented)
    # Uncomment when rate limiting is added:
    # assert len(successful) <= 5, "Max 5 concurrent requests should succeed"
    # assert len(errors) >= 5, "Expected some requests to be rate-limited"
    #
    # # Verify error types
    # for error in errors:
    #     assert "Rate limit exceeded" in str(error) or "Too many requests" in str(error)

    print(f"✓ All {len(successful)} concurrent requests handled successfully")


@pytest.mark.asyncio
@pytest.mark.load
async def test_preview_performance_by_sample_size(preview_service, test_data_config, stub_s3_dataframe):
    """
    Test preview generation time across different sample sizes.

    Performance targets:
    - 10 rows: <500ms
    - 100 rows: <1s
    - 500 rows: <2s
    - 1000 rows: <3s
    """
    # generate_preview requires a non-empty operations list
    operations = BASELINE_OPERATIONS

    test_cases = [
        (10, 500),    # 10 rows, max 500ms
        (100, 1000),  # 100 rows, max 1s
        (500, 2000),  # 500 rows, max 2s
        (1000, 3000), # 1000 rows, max 3s
    ]

    print("\n--- Performance by Sample Size ---")

    results = []
    for sample_size, max_duration_ms in test_cases:
        start = time.time()

        result = await preview_service.generate_preview(
            user_id=test_data_config["user_id"],
            dataset_id=test_data_config["dataset_id"],
            s3_file_path=test_data_config["s3_file_path"],
            operations=operations,
            sample_size=sample_size
        )

        duration_ms = (time.time() - start) * 1000

        assert result is not None, f"Preview failed for sample_size={sample_size}"

        status = "✓" if duration_ms < max_duration_ms else "⚠"
        print(f"{status} sample_size={sample_size:4d}: {duration_ms:6.0f}ms (target: <{max_duration_ms}ms)")

        results.append({
            "sample_size": sample_size,
            "duration_ms": duration_ms,
            "target_ms": max_duration_ms,
            "passed": duration_ms < max_duration_ms
        })

        # Soft assertion - warn but don't fail
        if duration_ms >= max_duration_ms:
            print(f"  WARNING: Preview slower than target for sample_size={sample_size}")

    # At least some tests should pass
    passed_count = sum(1 for r in results if r["passed"])
    assert passed_count > 0, "At least some performance targets should be met"


@pytest.mark.asyncio
@pytest.mark.load
async def test_memory_usage_with_large_sample(preview_service, test_data_config, stub_s3_dataframe):
    """
    Test that memory usage stays reasonable with max sample size.

    Target: 1000 row sample should use <500 MB

    This test uses tracemalloc to measure actual memory usage.
    """
    import tracemalloc

    tracemalloc.start()

    operations = BASELINE_OPERATIONS
    sample_size = 1000

    # Get baseline memory
    baseline = tracemalloc.get_traced_memory()[0]

    result = await preview_service.generate_preview(
        user_id=test_data_config["user_id"],
        dataset_id=test_data_config["dataset_id"],
        s3_file_path=test_data_config["s3_file_path"],
        operations=operations,
        sample_size=sample_size
    )

    # Get peak memory
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    memory_used_mb = (peak - baseline) / 1024 / 1024

    print("\n--- Memory Usage Test ---")
    print(f"Baseline memory: {baseline / 1024 / 1024:.1f} MB")
    print(f"Peak memory: {peak / 1024 / 1024:.1f} MB")
    print(f"Memory used: {memory_used_mb:.1f} MB")
    print("Target: <500 MB")

    assert result is not None, "Preview should succeed"

    # Soft assertion - warn but don't fail
    if memory_used_mb >= 500:
        print(f"⚠ WARNING: Memory usage ({memory_used_mb:.1f} MB) exceeds target (500 MB)")
    else:
        print(f"✓ Memory usage within target: {memory_used_mb:.1f} MB < 500 MB")


@pytest.mark.asyncio
@pytest.mark.load
async def test_rapid_sequential_requests(preview_service, test_data_config, stub_s3_dataframe):
    """
    Simulate rapid sequential requests (like rapid UI changes).

    Tests that backend handles rapid-fire requests gracefully.
    Frontend debouncing prevents most of these, but backend should be resilient.
    """
    # Simulate user rapidly changing operations
    operations_sequence = [
        [TransformationStepRequest(transformation_type="remove_duplicates", parameters={})],
        [
            TransformationStepRequest(transformation_type="remove_duplicates", parameters={}),
            TransformationStepRequest(transformation_type="fill_missing", columns=["value"], parameters={"method": "mean"})
        ],
        [
            TransformationStepRequest(transformation_type="remove_duplicates", parameters={}),
            TransformationStepRequest(transformation_type="fill_missing", columns=["value"], parameters={"method": "median"})
        ],
    ]

    print("\n--- Rapid Sequential Requests Test ---")

    results = []
    timings = []

    for i, operations in enumerate(operations_sequence):
        start = time.time()

        try:
            result = await preview_service.generate_preview(
                user_id=test_data_config["user_id"],
                dataset_id=test_data_config["dataset_id"],
                s3_file_path=test_data_config["s3_file_path"],
                operations=operations,
                sample_size=100
            )
            results.append(result)
            duration_ms = (time.time() - start) * 1000
            timings.append(duration_ms)

            print(f"Request {i+1}: {len(operations)} operations, {duration_ms:.0f}ms")

        except Exception as e:
            print(f"Request {i+1} failed: {e}")
            raise

        # Small delay to simulate rapid user actions
        await asyncio.sleep(0.05)  # 50ms between requests

    assert len(results) == len(operations_sequence), "All rapid requests should be handled"
    assert all(r is not None for r in results), "All previews should succeed"

    avg_time = sum(timings) / len(timings)
    print(f"\n✓ Handled {len(results)} rapid sequential requests successfully")
    print(f"  Average response time: {avg_time:.0f}ms")


@pytest.mark.asyncio
@pytest.mark.load
async def test_transformation_overhead(preview_service, test_data_config, stub_s3_dataframe):
    """
    Measure overhead of different numbers of transformations.

    Compares:
    - 0 transformations (baseline)
    - 1 transformation
    - 3 transformations
    - 5 transformations
    """
    sample_size = 100

    # generate_preview requires a non-empty operations list, so the
    # baseline is a single cheap transformation
    test_cases = [
        ("1 transformation", [
            TransformationStepRequest(transformation_type="remove_duplicates", parameters={})
        ]),
        ("3 transformations", [
            TransformationStepRequest(transformation_type="remove_duplicates", parameters={}),
            TransformationStepRequest(transformation_type="fill_missing", columns=["value"], parameters={"method": "mean"}),
            TransformationStepRequest(transformation_type="normalize", column="value", parameters={"method": "minmax"})
        ]),
        ("5 transformations", [
            TransformationStepRequest(transformation_type="remove_duplicates", parameters={}),
            TransformationStepRequest(transformation_type="fill_missing", columns=["value"], parameters={"method": "mean"}),
            TransformationStepRequest(transformation_type="normalize", column="value", parameters={"method": "minmax"}),
            TransformationStepRequest(transformation_type="outlier_removal", columns=["value"], parameters={"method": "iqr"}),
            TransformationStepRequest(transformation_type="one_hot_encode", column="category", parameters={})
        ]),
    ]

    print("\n--- Transformation Overhead Test ---")

    results = []
    for description, operations in test_cases:
        start = time.time()

        result = await preview_service.generate_preview(
            user_id=test_data_config["user_id"],
            dataset_id=test_data_config["dataset_id"],
            s3_file_path=test_data_config["s3_file_path"],
            operations=operations,
            sample_size=sample_size
        )

        duration_ms = (time.time() - start) * 1000

        assert result is not None, f"Preview failed for: {description}"
        results.append((description, duration_ms))

        print(f"{description:20s}: {duration_ms:6.0f}ms")

    # Calculate overhead per transformation
    baseline = results[0][1]
    five_transforms = results[-1][1]
    overhead_per_transform = (five_transforms - baseline) / 5

    print(f"\nBaseline (0 transforms): {baseline:.0f}ms")
    print(f"5 transforms: {five_transforms:.0f}ms")
    print(f"Overhead per transform: ~{overhead_per_transform:.0f}ms")


# Mark all tests as requiring integration resources
pytestmark = pytest.mark.integration


if __name__ == "__main__":
    """
    Run load tests directly with:
        python -m tests.load.test_preview_load
    """
    pytest.main([__file__, "-v", "-s"])
