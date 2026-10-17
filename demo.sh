#!/usr/bin/env bash
# Ride demo: backend in simulation mode + frontend. Usage: ./demo.sh [scenario] (default: trip-gorczewska-daszynskiego)
# Open http://localhost:5173 and use the "Demo" tab. Ctrl-C stops both. API_PORT changes the backend port.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
SCENARIO="${1:-trip-gorczewska-daszynskiego}"
PORT="${API_PORT:-8000}"

(cd backend && SIM_SCENARIO="$SCENARIO" uv run uvicorn main:app --port "$PORT") &
BACKEND=$!
trap 'kill "$BACKEND" 2>/dev/null || true' EXIT INT TERM

cd frontend
[ -d node_modules ] || npm install
VITE_API_URL="http://localhost:$PORT" npm run dev
