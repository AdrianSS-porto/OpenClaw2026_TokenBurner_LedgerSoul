#!/usr/bin/env bash
set -euo pipefail

curl -fsS "http://localhost:${PORT:-8000}/health"
