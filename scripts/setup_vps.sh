#!/usr/bin/env bash
set -euo pipefail

# Fresh VPS setup for LedgerSoul
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip docker.io docker-compose-plugin
sudo systemctl enable --now docker

echo "VPS setup complete. Next steps:"
echo "  cp .env.example .env"
echo "  docker compose up -d --build"
echo "  curl http://localhost:8000/health"
