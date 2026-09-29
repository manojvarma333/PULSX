#!/usr/bin/env bash
# Runs one benchmark case and prints REAL measured results (PRD section 44). No numbers
# in this output are ever hardcoded -- see benchmark/runner.py.
# Usage: ./scripts/benchmark.sh --events 1000000 --workers 4 --protocol binary --language cpp
set -euo pipefail
cd "$(dirname "$0")/.."

EVENTS=100000
WORKERS=1
PROTOCOL=json
LANGUAGE=python
STRATEGY=passthrough

while [[ $# -gt 0 ]]; do
    case "$1" in
        --events) EVENTS="$2"; shift 2 ;;
        --workers) WORKERS="$2"; shift 2 ;;
        --protocol) PROTOCOL="$2"; shift 2 ;;
        --language) LANGUAGE="$2"; shift 2 ;;
        --strategy) STRATEGY="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 1 ;;
    esac
done

DATASET="data/generated/market_data_${EVENTS}.csv"
if [ ! -f "$DATASET" ]; then
    echo "Generating $EVENTS events (dataset not found at $DATASET)..."
    ./scripts/generate_data.sh "$EVENTS"
fi

LAUNCH_MODE="process"
python -m benchmark.runner \
    --dataset "$DATASET" \
    --workers "$WORKERS" \
    --protocol "$PROTOCOL" \
    --language "$LANGUAGE" \
    --strategy "$STRATEGY" \
    --worker-launch-mode "$LAUNCH_MODE"
