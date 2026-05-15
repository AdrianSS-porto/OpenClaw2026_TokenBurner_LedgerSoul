#!/usr/bin/env bash
set -euo pipefail

mkdir -p state traces
./scripts/reset_state.sh

python -m ledgersoul.demo.run_scenario examples/scenarios/payment_failed.json
python -m ledgersoul.demo.run_scenario examples/scenarios/payment_recovered.json
python -m ledgersoul.demo.run_scenario examples/scenarios/high_value_refund.json
python -m ledgersoul.demo.run_scenario examples/scenarios/duplicate_webhook.json
python -m ledgersoul.demo.run_scenario examples/scenarios/suspicious_payment.json
python -m ledgersoul.demo.run_scenario examples/scenarios/api_failure.json

echo "Demo complete. Check traces/ and state/."
