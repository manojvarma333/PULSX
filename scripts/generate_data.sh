#!/usr/bin/env bash
# Generates synthetic market data at one of the standard sizes from PRD section 8.
# Usage: ./scripts/generate_data.sh <events> [extra generate_market_data.py args...]
# Example: ./scripts/generate_data.sh 1000000 --symbols 10 --seed 42
set -euo pipefail
cd "$(dirname "$0")/.."

EVENTS="${1:?usage: generate_data.sh <events> [extra args...]}"
shift || true

python tools/generate_market_data.py --events "$EVENTS" "$@"
