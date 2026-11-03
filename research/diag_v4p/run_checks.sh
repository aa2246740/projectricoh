#!/bin/zsh
set -eu
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diagv4p
/usr/bin/python3 -I -B -c 'import pathlib,plistlib,subprocess; v=plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil","info","-plist","/Volumes/Workspace"])); assert v["FilesystemType"]=="apfs" and v["VolumeUUID"]=="14BE04EB-AF49-497E-B36A-B078B2F7C5E8" and v["WritableVolume"]; pathlib.Path("/Volumes/Workspace/Scratch/tmp/projectricoh/diagv4p").mkdir(parents=True,exist_ok=True)'
runner=(/usr/bin/perl -e 'alarm 7200; exec @ARGV or die $!;' -- /usr/bin/nice -n 10 /usr/bin/sandbox-exec -f research/diag_v4p/offline.sb /usr/bin/python3 -I -B)
trap 'diag_exit=$?; /usr/bin/nice -n 10 /bin/ps -axo pid=,command= | "${runner[@]}" research/diag_v4p/process_receipt.py; "${runner[@]}" research/diag_v4p/cleanup.py; "${runner[@]}" research/diag_v4p/seal.py; exit "$diag_exit"' EXIT
"${runner[@]}" research/diag_v4p/scope.py
"${runner[@]}" firmware/engine_v61_diagv4p/build.py
"${runner[@]}" research/diag_v4p/host.py layout
"${runner[@]}" research/diag_v4p/native_refs.py
"${runner[@]}" research/diag_v4p/native_catalog.py
"${runner[@]}" research/diag_v4p/static_check.py
DIAGV4P_CASE=kernel "${runner[@]}" research/diag_v4p/kernel_check.py
for unit in 50mm 28mm mount; do
  DIAGV4P_CASE=rerun "${runner[@]}" research/diag_v4p/complete_model.py "$unit" --full-boot-pages
  DIAGV4P_CASE=readonly "${runner[@]}" research/diag_v4p/readonly_paths.py "$unit"
  DIAGV4P_CASE=cross-body "${runner[@]}" research/diag_v4p/cross_body.py "$unit"
  for case_name in cursors partial; do
    DIAGV4P_CASE=boundary-rerun "${runner[@]}" research/diag_v4p/boundaries.py "$unit" "$case_name"
  done
done
"${runner[@]}" research/diag_v4p/gate_cases.py positives
"${runner[@]}" research/diag_v4p/gate_cases.py mutations
"${runner[@]}" research/diag_v4p/compatibility.py
"${runner[@]}" research/diag_v4p/native_cases.py
"${runner[@]}" research/diag_v4p/cli_smoke.py
GXR_EMULATOR_BATCH=1 "${runner[@]}" research/diag_v4p/emu_boot.py
"${runner[@]}" research/diag_v4p/acceptance.py
