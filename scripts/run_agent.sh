#!/usr/bin/env bash
set -euo pipefail

uvicorn ledgersoul.server.api:app --host 0.0.0.0 --port "${PORT:-8000}"
