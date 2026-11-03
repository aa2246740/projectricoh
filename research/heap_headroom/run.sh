#!/bin/sh
set -eu

cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
heap_volume_facts=$(/usr/sbin/diskutil info -plist /Volumes/Workspace)
/usr/bin/python3 -I -B -c 'import plistlib,sys; d=plistlib.loads(sys.argv[1].encode()); assert d["VolumeUUID"]=="14BE04EB-AF49-497E-B36A-B078B2F7C5E8"; assert d["FilesystemType"]=="apfs" and d["MountPoint"]=="/Volumes/Workspace"; assert d["WritableVolume"] and d["WritableMedia"]; print("Workspace volume verified.")' "$heap_volume_facts"

/usr/bin/python3 -I -B research/heap_headroom/evidence.py check-inputs
/usr/bin/python3 -I -B research/heap_headroom/checkpoint.py --reader-check
/usr/bin/python3 -I -B research/heap_headroom/checkpoint.py
/usr/bin/python3 -I -B research/heap_headroom/static.py prepare
research/tooling_m32r/prefix/bin/m32r-elf-objdump -D -EB -b binary -m m32r --adjust-vma=0x2004b000 research/heap_headroom/local/main.bin > research/heap_headroom/local/main.asm.txt
research/tooling_m32r/prefix/bin/m32r-elf-objdump -D -EB -b binary -m m32r --adjust-vma=0x05000c00 research/heap_headroom/local/auxiliary.bin > research/heap_headroom/local/auxiliary.asm.txt
/usr/bin/python3 -I -B research/heap_headroom/static.py scan > research/heap_headroom/local/census-run.json
/usr/bin/python3 -I -B research/heap_headroom/budget.py > research/heap_headroom/local/budget-run.json
/usr/bin/python3 -I -B research/heap_headroom/evidence.py windows
/usr/bin/python3 -I -B research/heap_headroom/evidence.py labels
/usr/bin/python3 -I -B research/heap_headroom/evidence.py verify
/usr/bin/python3 -I -B research/heap_headroom/evidence.py manifest
