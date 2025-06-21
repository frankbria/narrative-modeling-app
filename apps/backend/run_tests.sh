#!/bin/bash
# Script to run backend tests with proper Python path

cd /home/frankbria/projects/narrative-modeling-app/apps/backend

# Set PYTHONPATH to include the backend directory
export PYTHONPATH=/home/frankbria/projects/narrative-modeling-app/apps/backend:$PYTHONPATH

# Run tests with uv
uv run pytest "$@"