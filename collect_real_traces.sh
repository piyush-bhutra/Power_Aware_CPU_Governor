#!/usr/bin/env bash
# One bounded profile; use only after separate experiment approval.
# Legacy positional arguments: <duration_s> <vm_bytes> [outdir].
# CPU example (NOT approved to execute):
# ./collect_real_traces.sh 5 64M --profile cpu --approved-workload
# No dd loop, no automatic multi-profile sequence; I/O profile disabled.
set -euo pipefail
cd -- "$(dirname -- "$0")"
exec .venv/bin/python -m benchmark.collect_traces "$@"
