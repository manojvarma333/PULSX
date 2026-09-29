#!/usr/bin/env bash
# Sets up a local Python virtualenv with all PulseX dependencies (PRD section 36).
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r backend/requirements.txt

echo ""
echo "Setup complete. Activate with: source .venv/bin/activate"
echo "Run tests with:                pytest"
echo "Generate sample data with:     ./scripts/generate_data.sh 10000"
