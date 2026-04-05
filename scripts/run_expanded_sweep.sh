#!/usr/bin/env bash
set -euo pipefail

OUTPUT_ROOT="${1:-/tmp/secure-delivery-expanded-sweep}"
MATRIX_PATH="${2:-configs/sweeps/article_extended_grid.json}"
REPLICATES="${3:-5}"

.venv/bin/python -m secure_delivery.cli run-sweep \
  --base-config-dir configs/experiments \
  --matrix "${MATRIX_PATH}" \
  --output-root "${OUTPUT_ROOT}" \
  --replicates "${REPLICATES}" \
  --seed-step 1
