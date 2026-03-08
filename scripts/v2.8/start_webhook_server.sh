#!/bin/bash

# Start Webhook Server for DeFi Risk Assessment Cache Monitoring

echo "🚀 Starting Webhook Server..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed or not in PATH"
    exit 1
fi

# Check if Flask is installed
if ! python3 -c "import flask" &> /dev/null; then
    echo "❌ Flask is not installed. Installing..."
    pip3 install flask
fi

# Check if webhook server is already running
if curl -s http://localhost:5001/webhook/health &> /dev/null; then
    echo "⚠️ Webhook server is already running on port 5001"
    echo "   Health check: http://localhost:5001/webhook/health"
    echo "   Status: http://localhost:5001/webhook/status"
    exit 0
fi

# Start the webhook server
echo "✅ Starting webhook server on port 5001..."
python3 webhook_server.py

echo "🛑 Webhook server stopped"
