#!/bin/sh
# Serial lane: one model process at a time; each stage has a wall-clock limit.
cd "$(dirname "$0")/../.."
L=research/emulator_batch/local
C="/usr/bin/python3 -I -B research/emulator_batch/cumulative.py"
stage() { name=$1; secs=$2; shift 2
  research/emulator_batch/limit.sh "$secs" "$L/cum-$name.out" $C "$@" || { echo "FAIL $name"; exit 1; }
  echo "done $name"; }
# Optional first argument: skip stages before the named one.
from=${1:-}
run() { name=$1
  if [ -n "$from" ] && [ "$name" != "$from" ]; then echo "skip $name"; return; fi
  from=""; stage "$@"; }
run regression 1800 regression
run regression-fast 1800 regression-fast
run boot-no-card 3600 boot --profile no-card
run boot-card 3600 boot --profile card
run acc-m2b 600 acceptance --milestone m2b
for c in files full read-error write-error no-card; do run files-$c 1800 files --case $c; done
run restart 3600 restart
run files-readback 1800 files --case readback
run model 1800 model
run guard 600 guard
run acc-m2c 600 acceptance --milestone m2c
echo ALL-DONE
