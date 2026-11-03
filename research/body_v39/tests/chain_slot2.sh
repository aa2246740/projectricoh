#!/bin/zsh
# Second test slot, run serially: Fn rotation (28mm, MOUNT), load routes, emulator boot.
# Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39 chain_slot2.sh
set -u
R=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
cd $R
L=research/body_v39/local/logs
PY="nice -n 10 /usr/bin/python3 -I -B"
for u in 28mm mount; do
  V39_PACKAGE=research/body_v39/local/fntest-package V39_ENGINE=firmware/engine_v58_g149/variants/fn-test \
    ${=PY} research/body_v39/tests/dat_rotate.py $u > $L/rotate-$u.log 2>&1; echo "rc=$?" >> $L/rotate-$u.log
done
for s in ctl ctl-bad no-card old-dat release; do
  ${=PY} research/body_v39/tests/load_routes.py 50mm $s > $L/load-$s.log 2>&1; echo "rc=$?" >> $L/load-$s.log
done
${=PY} research/body_v39/tests/emu_boot.py > $L/emu-boot.log 2>&1; echo "rc=$?" >> $L/emu-boot.log
echo done > $L/chain-slot2.done
