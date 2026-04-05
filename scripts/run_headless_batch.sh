#!/usr/bin/env bash
set -euo pipefail

OUTPUT_ROOT="${1:-/tmp/secure-delivery-batch}"

.venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments \
  --output-root "${OUTPUT_ROOT}"
