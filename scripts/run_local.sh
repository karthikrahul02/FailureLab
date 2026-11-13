#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if ! command -v python >/dev/null; then echo "Python 3.11+ is required." >&2; exit 1; fi
if ! command -v npm >/dev/null; then echo "Node.js/npm is required." >&2; exit 1; fi

if [[ ! -d "$ROOT_DIR/backend/.venv" ]]; then python -m venv "$ROOT_DIR/backend/.venv"; fi
source "$ROOT_DIR/backend/.venv/bin/activate"
pip install -e "$ROOT_DIR/backend[dev]"
(cd "$ROOT_DIR/backend" && uvicorn app.main:app --reload --port 8000) &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
cd "$ROOT_DIR/frontend"
npm install
npm run dev
