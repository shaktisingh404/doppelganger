#!/usr/bin/env bash
# Runs every smoke test in this folder. Run from backend/: ./tests/run_all.sh
set -e
cd "$(dirname "$0")/.."
for f in tests/test_*.py; do
  mod="${f%.py}"
  mod="${mod//\//.}"
  echo "=== $mod ==="
  python -m "$mod"
done
