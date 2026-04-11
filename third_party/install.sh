#!/bin/bash
# Install third-party dependencies for task automation system
# Only installs dependencies for the configured executor backend.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
load_env() {
    if [ -f "$PROJECT_ROOT/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    fi
}

echo "Installing third-party dependencies..."

# Load env first
load_env

executor_backend="${EXECUTOR_BACKEND:-opencode}"
echo "Executor backend: $executor_backend"

# Node.js dependencies (only for opencode)
if [ "$executor_backend" = "opencode" ]; then
    echo ""
    echo "=== Node.js Dependencies (OpenCode SDK) ==="
    cd "$SCRIPT_DIR/nodejs"
    npm install
    echo "✅ Node.js dependencies installed."
else
    echo ""
    echo "=== Skipping Node.js Dependencies ==="
    echo "Executor backend is '$executor_backend', Node.js SDK not required."
fi

echo ""
echo "=== Installation Complete ==="
echo "Third-party dependencies installed successfully."
