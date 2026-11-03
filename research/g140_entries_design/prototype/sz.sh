#!/bin/bash
# Size-only prototype compile (g140 design). Usage: sz.sh <out-name> <source.c>
set -e
ROOT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
S=/Volumes/Workspace/Scratch/tmp/projectricoh/g140-design
export TMPDIR=$S
GCC=$ROOT/research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc
OD=$ROOT/research/tooling_m32r/prefix/bin/m32r-elf-objdump
P=$ROOT/firmware/engine_v56_g139/candidate/containers/product
F=(-std=c11 -Oz -ffreestanding -fno-builtin -fno-stack-protector -fno-common -fpic -m32r -mmodel=medium
   -msdata=none -G0 -Wall -Wextra -fno-unwind-tables -fno-asynchronous-unwind-tables -fvisibility=hidden
   -ffunction-sections -fdata-sections -falign-functions=4 -fno-partial-inlining -fno-ipa-sra
   -fno-inline-small-functions)
nice -n 10 "$GCC" "${F[@]}" -I"$P" -I"$P/src/firmware/engine/core" -I"$S/proto" -c "$2" -o "$S/obj/$1.o"
"$OD" -t "$S/obj/$1.o" | awk '$2=="g"||$2=="l"{print}' | grep -E '\.(text|rodata|bss|data)' | \
  awk '{print $(NF-1), $NF, $(NF-2)}' > "$S/obj/$1.syms"
"$OD" -h "$S/obj/$1.o" | awk '/\.(text|rodata|bss|data)/{print $2, $3}' > "$S/obj/$1.sec"
python3 -I -c "
import sys
t={'text':0,'rodata':0,'bss':0,'data':0}
for l in open(sys.argv[1]):
    n,s=l.split()
    for k in t:
        if n.startswith('.'+k): t[k]+=int(s,16)
print(sys.argv[2], t)
" "$S/obj/$1.sec" "$1"
