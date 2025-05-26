#!/bin/bash
set -e

echo "🧪 Running all tests..."

echo "🔍 Running linting..."
uv run black --check app tests *.py
uv run ruff check app tests *.py

echo "🔧 Running type checking..."
uv run mypy app

echo "🧪 Running tests with coverage..."
uv run pytest -v --cov=app --cov-report=term-missing

echo ""
echo "✅ All tests passed!"