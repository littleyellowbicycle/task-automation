#!/bin/bash
# Start the WeChat Task Automation System
# This script checks and installs dependencies before starting the application.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THIRD_PARTY_DIR="$SCRIPT_DIR/third_party"

# Load environment variables from .env if exists
load_env() {
    if [ -f "$SCRIPT_DIR/.env" ]; then
        echo "📄 Loading environment variables from .env..."
        export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
    fi
}

# Check if Node.js dependencies are installed (only for opencode executor)
check_node_deps() {
    local executor_backend="${EXECUTOR_BACKEND:-opencode}"
    
    # Only install Node.js deps if using opencode executor
    if [ "$executor_backend" != "opencode" ]; then
        echo "ℹ️  Executor backend: $executor_backend (skipping Node.js dependencies)"
        return 0
    fi
    
    echo "ℹ️  Executor backend: $executor_backend"
    
    if [ ! -d "$THIRD_PARTY_DIR/nodejs/node_modules" ]; then
        echo "📦 Node.js dependencies not found. Installing..."
        cd "$THIRD_PARTY_DIR/nodejs"
        npm install
        echo "✅ Node.js dependencies installed."
    else
        echo "✅ Node.js dependencies already installed."
    fi
}

# Main
echo "🚀 Starting WeChat Task Automation System..."
echo ""

load_env
check_node_deps

echo ""
echo "Starting application..."
cd "$SCRIPT_DIR"
python main.py "$@"
