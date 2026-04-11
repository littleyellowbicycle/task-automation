# Third-Party Dependencies

This directory contains installation scripts and configuration for third-party dependencies.

## Directory Structure

```
third_party/
├── install.sh              # Installation script
├── nodejs/
│   ├── package.json        # Node.js dependencies config
│   └── node_modules/       # Installed packages (git-ignored)
└── README.md
```

## Dependencies by Executor Backend

| Backend | Required Dependencies |
|---------|----------------------|
| opencode | Node.js SDK (`@opencode-ai/sdk`) |
| openhands | None (uses HTTP API) |
| openclaw | None (uses HTTP API) |

## Installation

### Automatic (Recommended)

```bash
# In WSL
cd /mnt/d/project/task-automation
./start.sh
```

The `start.sh` script will:
1. Load environment variables from `.env`
2. Check `EXECUTOR_BACKEND` setting
3. Install dependencies only if needed

### Manual

```bash
# Install all dependencies
cd third_party
./install.sh

# Or install Node.js deps manually
cd third_party/nodejs
npm install
```

## Configuration

Set the executor backend in `.env`:

```bash
# Options: opencode, openhands, openclaw
EXECUTOR_BACKEND=opencode
```

## Git Ignore

The `node_modules/` directory is git-ignored. Run `./start.sh` or `./install.sh` after cloning.
