#!/bin/sh
# Local-only CI: baseline candidate spec review output-json
# Status: 0 ACCEPT, 3 BLOCK, 4 REVIEW, 5 INCONCLUSIVE, 2 configuration/input error.
# No deployment, provisioning, download or production mutation.
set -eu
exec python -m sourceroi --project "$2" release-check \
  --baseline "$1" --spec "$3" --approval "$4" --output "$5" \
  --max-calls 8 --max-seconds 60 --allow-model-calls
