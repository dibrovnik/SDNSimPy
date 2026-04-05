#!/usr/bin/env bash
set -euo pipefail

OUTPUT_ROOT="${1:-/tmp/secure-delivery-batch-30x}"
REPLICATES="${2:-30}"

.venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments \
  --output-root "${OUTPUT_ROOT}" \
  --replicates "${REPLICATES}" \
  --seed-step 1
