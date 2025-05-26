#!/bin/bash
set -e

echo "🧪 Running all tests..."

echo "🔍 Running linting..."
uv run black --check app models schemas tests *.py
uv run ruff check app models schemas tests *.py

echo "🔧 Running type checking..."
uv run mypy app models schemas

echo "🧪 Running tests with coverage..."
uv run pytest -v --cov=app --cov=models --cov=schemas --cov-report=term-missing

echo ""
echo "✅ All tests passed!"