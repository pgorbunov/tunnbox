#!/bin/bash
# Runs the full local test suite: backend tests, frontend type-check and build.
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/3] Backend tests"
(cd backend && WG_BACKEND_MODE=mock ${PYTHON:-python3} -m pytest -q)

echo "[2/3] Frontend type-check"
(cd frontend && npm run check)

echo "[3/3] Frontend build"
(cd frontend && npm run build)

echo "All checks passed."
