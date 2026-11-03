#!/bin/sh
# limit.sh SECONDS LOG cmd...: run cmd with a wall-clock limit, output to LOG.
secs=$1; log=$2; shift 2
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-batch
exec perl -e 'alarm shift; exec @ARGV; die "exec: $!"' "$secs" "$@" > "$log" 2>&1
