#!/bin/bash
# Run unit tests that don't require MongoDB

echo "Running unit tests (no database required)..."
uv run pytest \
    tests/test_security/ \
    tests/test_processing/ \
    tests/test_utils/ \
    tests/test_model_training/test_problem_detector.py \
    tests/test_model_training/test_feature_engineer.py \
    -v --tb=short