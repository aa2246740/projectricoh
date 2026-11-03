#!/bin/zsh
# Second test slot, part 2: the g139 host checks that touch code gen 149 changed
# (ig_menu preselect/offer, OK on the offered row, apply/lock/record paths whose
# grain clear moved into core_call), run against v3.9 + gen 149.
# Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39 chain_slot2b.sh
set -u
R=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
cd $R
L=research/body_v39/local/logs
PY="nice -n 10 /usr/bin/python3 -I -B"
${=PY} research/body_v39/tests/g139_check_v39.py cold-none offer offer-ok offer-adj offer-half offer-move-ok \
  offer-disp offer-unconfirmed p101-normal held-lock tail-own record-busy t-error value-ends --unit 50mm \
  > $L/g139-check-50mm.log 2>&1; echo "rc=$?" >> $L/g139-check-50mm.log
for u in 28mm mount; do
  ${=PY} research/body_v39/tests/g139_check_v39.py offer offer-ok offer-disp p101-normal held-lock --unit $u \
    > $L/g139-check-$u.log 2>&1; echo "rc=$?" >> $L/g139-check-$u.log
done
echo done > $L/chain-slot2b.done
