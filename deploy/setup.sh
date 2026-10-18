#!/usr/bin/env bash
# One-shot, repeatable setup of WarsawOpenData on a fresh Ubuntu 24.04 machine (e.g. a RunPod pod), as root.
# Installs the toolchain, clones / updates the repo, pulls the LFS data, builds the C++ router and the frontend and
# precomputes every data file the server needs (GTFS / OSM caches, StationLocations, street graphs, RAPTOR timetable,
# street matrices). Safe to run again: every step skips what is already up to date.
#
#   curl -fsSL .../deploy/setup.sh | bash          # or: bash deploy/setup.sh
#   REPO_DIR=/root/WarsawOpenData BRANCH=main THREADS=16 bash deploy/setup.sh
#
# Needs: git access to the repo (SSH key or token). Put the API keys into $REPO_DIR/.env (see ACCESS.md).
set -euo pipefail
REPO_URL=${REPO_URL:-git@github.com:szymon-hajderek/WarsawOpenData.git}
REPO_DIR=${REPO_DIR:-/root/WarsawOpenData}
BRANCH=${BRANCH:-main}
THREADS=${THREADS:-$(nproc)}
log() { echo "[setup $(date +%H:%M:%S)] $*"; }

log "system packages (git-lfs, g++-14, node, build tools)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git git-lfs cmake g++-14 build-essential curl ca-certificates python3 >/dev/null
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
git lfs install --skip-repo >/dev/null

log "repo $REPO_URL ($BRANCH) -> $REPO_DIR"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch -q origin && git -C "$REPO_DIR" checkout -q "$BRANCH" && git -C "$REPO_DIR" pull -q --ff-only origin "$BRANCH"
else
  git clone -q --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"
git lfs pull

log "backend Python deps (uv sync)"
(cd backend && uv sync -q)

log "C++ street router (g++-14, Release)"
cmake -S algorithms/router -B algorithms/router/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++-14 >/dev/null
cmake --build algorithms/router/build -j"$THREADS" >/dev/null

log "frontend (npm ci + production build)"
(cd frontend && npm ci --no-audit --no-fund --loglevel=error && npm run build >/dev/null)

log "data: GTFS / OSM caches, StationLocations, street graphs and matrices (threads=$THREADS, ~10-20 min the first time)"
(cd backend && uv run python -u preprocess_street.py --threads "$THREADS" 2>&1 | tr '\r' '\n' | grep -E "points|done|mode|Traceback" || true)
log "data: RAPTOR timetable"
(cd backend && uv run python -c "import preprocess_transit as t; print(t.build() if t.stale() else 'timetable up to date')")

[ -f .env ] || log "WARNING: no .env (PORTAL_KEY etc.): live vehicles / delays will answer 503. See ACCESS.md."
log "done. Start with: bash deploy/run.sh"
