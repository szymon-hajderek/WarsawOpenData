#!/usr/bin/env bash
# Start the app after deploy/setup.sh: the backend (it starts the C++ router itself) on 127.0.0.1:8000 and the
# production frontend (`vite preview`, proxying /api to the backend) on 0.0.0.0:$PORT. Logs in $REPO_DIR/logs/.
# Expose $PORT (default 8080) as an HTTP port of the pod; the app is then at https://<pod-id>-<port>.proxy.runpod.net
#
#   bash deploy/run.sh            # start (restarts if already running)
#   bash deploy/run.sh stop
set -euo pipefail
REPO_DIR=${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
PORT=${PORT:-8080}
export PATH="$HOME/.local/bin:$PATH"
cd "$REPO_DIR"; mkdir -p logs

stop() {
  for f in logs/backend.pid logs/frontend.pid; do
    [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"
  done
  pkill -f "^$REPO_DIR/algorithms/router/build/street_router serve" 2>/dev/null || true
  sleep 1
}
stop
[ "${1:-}" = stop ] && { echo "stopped"; exit 0; }

(cd backend && nohup uv run uvicorn main:app --host 127.0.0.1 --port 8000 > ../logs/backend.log 2>&1 & echo $! > ../logs/backend.pid)
(cd frontend && nohup npx vite preview --host 0.0.0.0 --port "$PORT" --strictPort > ../logs/frontend.log 2>&1 & echo $! > ../logs/frontend.pid)

echo "waiting for the backend and the router (logs/backend.log)..."
for _ in $(seq 120); do
  grep -qE "street router: serving|Traceback|did not start" logs/backend.log 2>/dev/null && break; sleep 3
done
grep -E "street router: serving|Traceback|did not start" logs/backend.log | tail -2
curl -fsS -m 10 "http://127.0.0.1:$PORT/api/stations/health" >/dev/null && echo "up: http://0.0.0.0:$PORT (API via /api)" \
  || echo "frontend or API not answering yet: see logs/"
