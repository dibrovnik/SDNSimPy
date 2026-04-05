#!/usr/bin/env bash
set -euo pipefail

BATCH_ROOT="${1:-/tmp/secure-delivery-batch}"
ARTICLE_DIR="${2:-/tmp/secure-delivery-article-tables}"
PLOTS_DIR="${3:-/tmp/secure-delivery-batch-plots}"

.venv/bin/python -m secure_delivery.cli export-article \
  --input-root "${BATCH_ROOT}" \
  --output-dir "${ARTICLE_DIR}"

MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots \
  --input-dir "${BATCH_ROOT}" \
  --output-dir "${PLOTS_DIR}"
