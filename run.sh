#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

source .venv/bin/activate

if [ ! -f ".env" ]; then
    echo "No .env file found. Run ./setup.sh first."
    exit 1
fi

echo "Starting Token Optimizer on http://127.0.0.1:8765"
exec uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
