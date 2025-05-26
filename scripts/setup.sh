#!/bin/bash
set -e

echo "🚀 Setting up Zapa development environment..."

# Check for required tools
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Set up Python service
echo "🐍 Setting up backend service..."
uv venv
uv pip install -e ".[dev]"

echo "✅ Setup complete!"
echo ""
echo "To run tests:"
echo "  ./scripts/test-all.sh"
echo ""
echo "To run services:"
echo "  # Private service (internal/admin):"
echo "  uv run uvicorn private_main:app --reload --port 8001"
echo "  # Public service (user-facing):"
echo "  uv run uvicorn public_main:app --reload --port 8002"