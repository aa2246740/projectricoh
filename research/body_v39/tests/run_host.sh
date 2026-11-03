#!/bin/zsh
# Build and run host_v39.c against the formal sources (read only):
# firmware/engine_v59_g151/resident (== firmware/resident_v39/resident) and
# firmware/engine_v59_g151/candidate/engine_services.
# Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39 run_host.sh <out.jsonl>
set -eu
R=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
HERE=${0:A:h}
OUT=${1:A}
E=${V39_ENGINE_ROOT:-$R/firmware/engine_v59_g151}
T=${TMPDIR:?}/host-v39
rm -rf $T; mkdir -p $T
for f in $E/resident/*.[ch]; do cmp -s $f $R/firmware/resident_v39/resident/${f:t} || { echo "resident copy differs: ${f:t}"; exit 3; }; done
clang -std=c11 -O1 -g -Wall -Wextra -Wno-unused-function -Wno-unused-parameter -D_FORTIFY_SOURCE=0 -U__OPTIMIZE__ \
  -fsanitize=address,undefined -fno-sanitize-recover=all -DRV_HOST \
  -I$E/resident -I$E/candidate/engine_services \
  $HERE/host_v39.c $E/resident/{resident,shared,hooks,loader,validate_envelope.inc}.c \
  $E/candidate/engine_services/{services,api,native_seed}.c -o $T/host_v39
: > $OUT
for g in caps handshake disabled epochs h09 h10 image restore lane check header discard; do
  ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
    nice -n 10 $T/host_v39 $g >> $OUT || { echo "group $g failed rc=$?"; exit 1; }
done
echo "ok $(wc -l < $OUT) lines"
