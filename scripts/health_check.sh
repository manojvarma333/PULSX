#!/usr/bin/env bash
# Checks the health of the running Dockerized stack (PRD section 41).
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

echo "Checking backend at $BACKEND_URL/health ..."
if curl -fsS "$BACKEND_URL/health"; then
    echo ""
    echo "Backend is reachable."
else
    echo "Backend health check FAILED (is 'docker compose up' running?)" >&2
    exit 1
fi
