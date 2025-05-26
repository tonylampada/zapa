#!/bin/bash
set -e

echo "🧪 Running integration tests..."
echo ""
echo "⚠️  WARNING: Integration tests require external services to be running!"
echo ""

# Check if WhatsApp Bridge is running
if [ "$1" == "whatsapp" ] || [ "$1" == "all" ]; then
    echo "Testing WhatsApp Bridge integration..."
    if ! curl -s http://localhost:3000/health > /dev/null; then
        echo "❌ WhatsApp Bridge not running on port 3000"
        echo "   Start it with: docker run -p 3000:3000 zapw/zapw"
        exit 1
    fi
    
    cd backend
    INTEGRATION_TEST_WHATSAPP=true uv run pytest tests/integration/adapters/test_whatsapp_integration.py -v -s
    cd ..
fi

# Future: Add other integration tests (LLM providers, etc.)

echo ""
echo "✅ Integration tests completed!"