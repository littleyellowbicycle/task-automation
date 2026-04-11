#!/bin/bash
# One-click start with ngrok tunnel
# Usage: ./start_with_ngrok.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/ngrok_$(date +%Y%m%d_%H%M%S).log"
PID_FILE="/tmp/ngrok.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Task Automation - Starting with ngrok Tunnel          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check ngrok installation
echo -e "${BLUE}[1/5] Checking ngrok installation...${NC}"
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}❌ ngrok not installed!${NC}"
    echo ""
    echo "Please install ngrok first:"
    echo "  curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
    echo "  echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list"
    echo "  sudo apt update && sudo apt install ngrok"
    echo ""
    echo "Then configure your authtoken:"
    echo "  ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    echo "Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi
echo -e "${GREEN}   ✅ ngrok is installed${NC}"

# Check authtoken
echo -e "${BLUE}[2/5] Checking ngrok configuration...${NC}"
if ! ngrok config check &> /dev/null; then
    echo -e "${RED}❌ ngrok authtoken not configured!${NC}"
    echo ""
    echo "Please configure your authtoken:"
    echo "  ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    echo "Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi
echo -e "${GREEN}   ✅ ngrok authtoken configured${NC}"

# Stop existing ngrok if running
echo -e "${BLUE}[3/5] Setting up ngrok tunnel...${NC}"
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "   Stopping existing ngrok process..."
    kill $(cat "$PID_FILE") 2>/dev/null || true
    sleep 2
fi

# Start ngrok
echo "   Starting ngrok on port 8086..."
ngrok http 8086 --log=stdout > "$LOG_FILE" 2>&1 &
NGROK_PID=$!
echo $NGROK_PID > "$PID_FILE"
sleep 3

# Verify ngrok is running
if ! kill -0 $NGROK_PID 2>/dev/null; then
    echo -e "${RED}❌ Failed to start ngrok${NC}"
    echo "Check log: cat $LOG_FILE"
    exit 1
fi

# Get public URL
echo -e "${BLUE}[4/5] Getting public URL...${NC}"
PUBLIC_URL=""

for i in {1..15}; do
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o 'https://[^"]*\.ngrok[^"]*' | head -1)
    if [ -n "$PUBLIC_URL" ]; then
        break
    fi
    echo "   Waiting for ngrok tunnel... ($i/15)"
    sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
    echo -e "${RED}❌ Failed to get ngrok public URL${NC}"
    echo "Check ngrok status: curl http://localhost:4040/api/tunnels"
    echo "Check log: cat $LOG_FILE"
    exit 1
fi

echo -e "${GREEN}   ✅ Public URL: $PUBLIC_URL${NC}"

# Update .env
ENV_FILE="$SCRIPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    # Remove existing PUBLIC_CALLBACK_URL
    grep -v "^PUBLIC_CALLBACK_URL=" "$ENV_FILE" > "${ENV_FILE}.tmp" 2>/dev/null || true
    mv "${ENV_FILE}.tmp" "$ENV_FILE" 2>/dev/null || true
fi
echo "PUBLIC_CALLBACK_URL=$PUBLIC_URL" >> "$ENV_FILE"
echo -e "${GREEN}   ✅ Updated .env with PUBLIC_CALLBACK_URL${NC}"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🌐 Public URLs for Feishu                               ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Callback Base: ${PUBLIC_URL}              ${NC}"
echo -e "${GREEN}║  Approve: ${PUBLIC_URL}/decision?task_id=xxx&action=approve  ${NC}"
echo -e "${GREEN}║  Reject:  ${PUBLIC_URL}/decision?task_id=xxx&action=reject   ${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Start application
echo -e "${BLUE}[5/5] Starting application...${NC}"
echo ""

cd "$SCRIPT_DIR"

# Check if start.sh exists
if [ ! -f "$SCRIPT_DIR/start.sh" ]; then
    echo -e "${RED}❌ start.sh not found at $SCRIPT_DIR/start.sh${NC}"
    echo "Current directory: $(pwd)"
    echo "Files in current directory:"
    ls -la
    exit 1
fi

# Source the start script instead of exec to preserve environment
bash "$SCRIPT_DIR/start.sh" "$@"
