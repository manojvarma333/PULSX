#!/usr/bin/env bash
# Stops the Dockerized stack.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose down
