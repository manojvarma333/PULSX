#!/usr/bin/env bash
# Starts the Dockerized stack (postgres + backend + frontend). PRD section 35.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example -- edit it before running in anything but local dev."
fi

docker compose up --build -d
echo ""
echo "Backend:  http://localhost:8000/health"
echo "Frontend: http://localhost:5173"
