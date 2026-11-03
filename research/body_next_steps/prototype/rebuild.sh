#!/bin/zsh
# Rebuild and strict-link the body-next-steps variants in Scratch.
# Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-next-steps rebuild.sh
# Inputs (read only): firmware/resident_v38 (sources + ignored local/resident
# linked_hooks.S, trust.c), research/body_next_plan prototype/r2 diffs and its
# ignored local/prototype/r2 trampoline diffs, and the diffs in this directory.
set -eu
R=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
P=$R/research/body_next_steps/prototype
PLAN=$R/research/body_next_plan
S=${TMPDIR:?}/v
mkdir -p $S
fresh() {
  rm -rf $S/$1; mkdir -p $S/$1
  cp $R/firmware/resident_v38/resident/*.{c,h,S} $R/firmware/resident_v38/resident/resident.ld $S/$1/
  cp $R/firmware/resident_v38/local/resident/{linked_hooks.S,trust.c} $S/$1/
  rm -f $S/$1/v3_checks.c
  sed 's#firmware/resident_v38/resident/resident.ld#a/resident.ld#' $PLAN/prototype/r2/base-ld.diff | (cd $S/$1 && patch -s -p1)
}
copy() { rm -rf $S/$2; cp -R $S/$1 $S/$2; rm -rf $S/$2/build; }
fresh base
for v in vH vS1; do
  fresh $v
  (cd $S/$v && patch -s -p1 < $PLAN/prototype/r2/$v.c.diff && patch -s -p1 < $PLAN/local/prototype/r2/$v.linked_hooks.diff)
done
apply() { copy $1 $2; (cd $S/$2 && patch -s -p1 < $3); }
apply vS1 c1 $P/c1-vs-vS1.diff
apply vS1 c2 $P/c2-vs-vS1.diff
for v in r3 r3b r4 rN; do apply vS1 $v $P/$v-vs-vS1.diff; done
copy c1 r1; cp $S/c2/validate_envelope.inc.c $S/r1/
for c in c4 c5 c6 c7 c8; do apply r1 $c $P/$c-vs-r1.diff; done
copy r3 r2; cp $S/vS1/bridges.S $S/r2/
copy r3 neg80; copy r3 neg81
sed -i '' 's/RV_PLANNING_MARGIN = 24;/RV_PLANNING_MARGIN = 80;/' $S/neg80/resident.ld
sed -i '' 's/RV_PLANNING_MARGIN = 24;/RV_PLANNING_MARGIN = 81;/' $S/neg81/resident.ld
# review_body_reclaim fixes, applied to r3 by r2fix.py
fix() { copy r3 $1; python3 -I $P/r2fix.py $S/$1 $2; }
fix f_cap cap; fix f_args args; fix f_done done; fix f_frz freeze; fix f_frzcp freezecp
fix f_wide wide; fix f_inl inline; fix r5b cap,args,done; fix r6a cap,args,done,freezecp,wide
fix r7 cap,args,done,freezecp,wide,inline; fix r7b cap,args,done,wide,inline; fix r7n cap,args,done,freezecp,inline
copy r7 neg44; copy r7 neg45
sed -i '' 's/RV_PLANNING_MARGIN = 24;/RV_PLANNING_MARGIN = 44;/' $S/neg44/resident.ld
sed -i '' 's/RV_PLANNING_MARGIN = 24;/RV_PLANNING_MARGIN = 45;/' $S/neg45/resident.ld
for v in base vH vS1 c1 c2 r1 c4 c5 c6 c7 c8 r2 r3 r3b r4 rN neg80 neg81 \
         f_cap f_args f_done f_frz f_frzcp f_wide f_inl r5b r6a r7 r7b r7n neg44 neg45; do
  (cd $S/.. && python3 -I $P/proto_strict.py v/$v rv_resume_10=0x202b1210 >/dev/null)
done
python3 -I $P/collect.py $S ${1:-$TMPDIR/sizes.json}
echo "wrote ${1:-$TMPDIR/sizes.json}"
