#!/usr/bin/env bash
# Standalone interactive launcher. Never bypass its confirmation prompt.
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  printf '%s\n' 'Missing executable .venv/bin/python; no workload started.' >&2
  exit 1
fi
cd -- "$PROJECT_ROOT"
exec "$PROJECT_ROOT/.venv/bin/python" -m benchmark.safe_cpu_launcher "$@"
