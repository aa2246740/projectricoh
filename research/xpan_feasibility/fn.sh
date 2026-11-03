#!/bin/sh
# Read-only: print disassembly from VMA $2 for $3 lines of firmware $1 (ilaunch3|jlaunch3).
D=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/tooling_m32r/disasm
f=$(grep -l "^$2:" $D/$1-sec*.disasm.txt | head -1)
awk -v s="$2:" -v n="${3:-40}" 'index($0,s)==1{f=1} f{print; if(++c>=n) exit}' "$f" | cut -c1-90
