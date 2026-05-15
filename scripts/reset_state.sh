#!/usr/bin/env bash
set -euo pipefail

mkdir -p state traces
rm -f state/*.json state/*.jsonl traces/*.json
touch state/.gitkeep traces/.gitkeep

echo "State and traces reset."
