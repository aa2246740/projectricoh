#!/bin/sh
set -eu
evidence=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/studio_gpu_r1/fix_r4
python=/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/.venv/bin/python
for scenario in "$@"
do
    TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r3/ nice -n 10 "$python" -I -B "$evidence/verify.py" --timeout 300 "final-$scenario" -- "$python" -I -B "$evidence/replay.py" "$scenario"
done
