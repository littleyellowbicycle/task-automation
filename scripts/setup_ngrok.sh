#!/bin/bash
# Setup ngrok for public URL tunneling
# This allows Feishu to callback to your local application

set -e

echo "=== ngrok Setup Script ==="
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    echo ""
    echo "Please run the following commands manually in WSL:"
    echo ""
    echo "  1. Download and install ngrok:"
    echo "     curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
    echo "     echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list"
    echo "     sudo apt update && sudo apt install ngrok"
    echo ""
    echo "  2. Sign up at https://ngrok.com and get your authtoken"
    echo ""
    echo "  3. Configure ngrok:"
    echo "     ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    exit 1
fi

echo "✅ ngrok is installed: $(ngrok version)"
echo ""

# Check if authtoken is configured
if ! ngrok config check &> /dev/null; then
    echo "⚠️  ngrok authtoken not configured!"
    echo ""
    echo "Please run:"
    echo "  ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    echo "Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi

echo "✅ ngrok authtoken is configured"
echo ""

# Start ngrok
echo "🚀 Starting ngrok tunnel on port 8086..."
echo ""
echo "Public URL will be shown below. Add it to your .env file:"
echo "  PUBLIC_CALLBACK_URL=https://xxx.ngrok.io"
echo ""
echo "Press Ctrl+C to stop the tunnel."
echo ""

ngrok http 8086
