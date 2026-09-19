#!/usr/bin/env bash
# Collect real /proc/stat traces under stress-ng load, one CSV per profile.
# usage: collect_real_traces.sh <duration_s> <vm_bytes> [outdir]
#   e.g. collect_real_traces.sh 20 256M      (dry run)
set -euo pipefail
DUR=${1:?duration seconds}; VMB=${2:?--vm-bytes value, e.g. 256M}
OUT=${3:-data/real_traces}
RAMP=10; COOL=10
IO_FILE="$HOME/io_test_file"
trap 'pkill -P $$ 2>/dev/null || true; rm -f "$IO_FILE"' EXIT   # no stray dd loop if the script dies
cd "$(dirname "$0")"
PY=.venv/bin/python
mkdir -p "$OUT"

# half of VMB for the mixed profile (supports K/M/G suffix or plain bytes)
num=${VMB%[KkMmGgBb]}; suf=${VMB#"$num"}
HALF="$((num / 2))$suf"

# Default cpu/vm methods SIGILL on this VM (they emit AVX-512, which the guest lacks),
# leaving those profiles idle. Pin methods that run cleanly.
CPUM="--cpu-method int64"; VMM="--vm-method flip"

# Profile status (see docs/vm_feasibility.md, "VirtualBox/AMD Zen 4 timing issues"):
#   io         - VERIFIED (~5.9% iowait).
#   cpu        - VERIFIED after the --paravirtprovider legacy fix: a 5 s 4-worker run
#                took 5.15 s wall-clock (includes stress-ng startup), and /proc/stat
#                advanced 782 jiffies over 2 s (~800 expected). Discard pre-fix traces.
#   vm         - UNVERIFIED: no SIGILL, but measured only ~9% util in dry run.
#   mixed      - UNVERIFIED: uses the same cpu/vm stressors.
declare -A CMD=(
  [cpu]="--cpu 4 $CPUM"      # VERIFIED post-paravirt-fix: 5.15 s for 5 s, 782/~800 jiffies
  [io]="dd direct-I/O loop"   # special-cased below: stress-ng --hdd SIGILLs on this VM
  [vm]="--vm 1 --vm-bytes $VMB $VMM"   # UNVERIFIED - measured only ~9% util in dry run
  [mixed]="--cpu 2 $CPUM --io 1 --vm 1 --vm-bytes $HALF $VMM"
  [idle]=""
)

for p in cpu io vm mixed idle; do
  echo "== $p: ${CMD[$p]:-<no load>}"
  rm -f "$OUT/$p.csv"   # log_csv appends; start clean
  pid=""
  if [[ $p == io ]]; then
    # dd loop runs until killed (stress-ng handles its own --timeout)
    ( while true; do
        dd if=/dev/zero of="$IO_FILE" bs=1M count=8 oflag=direct conv=fsync 2>/dev/null
      done ) &
    pid=$!
  elif [[ -n "${CMD[$p]}" ]]; then
    # timeout covers ramp + collection + margin
    stress-ng ${CMD[$p]} --timeout $((RAMP + DUR + 5))s >/dev/null 2>&1 &
    pid=$!
  fi
  sleep "$RAMP"
  $PY governor.py --interval 1 --ticks "$DUR" --csv "$OUT/$p.csv"
  if [[ $p == io ]]; then
    pkill -P "$pid" 2>/dev/null || true; kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true; rm -f "$IO_FILE"
  elif [[ -n "$pid" ]]; then
    wait "$pid" || true
  fi
  sleep "$COOL"
done
echo "done -> $OUT"
