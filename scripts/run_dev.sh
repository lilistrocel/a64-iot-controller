#!/bin/bash
#
# A64 IoT Controller - Development Run Script
#
# Runs the controller in development mode with auto-reload.
#
# Usage: bash run_dev.sh
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Installing dependencies..."
    ./venv/bin/pip install -r requirements.txt
fi

# Activate virtual environment and run
echo "Starting A64 IoT Controller in development mode..."
echo ""

./venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
