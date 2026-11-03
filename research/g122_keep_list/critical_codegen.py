"""Check the two compiled loop limits in the final ELF."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,DAT,save,file_sha

elf=TREE/'candidate/local/full-r13/engine.elf'
rows=[]
for symbol,checks in (
    ('ig_apply',('ldi r4,#16 -> st r4,@sp','ld r5,@sp -> addi r5,#-1')),
    ('a4_move',('ldi fp,#16','addi fp,#-1','beqz fp,'))):
    result=subprocess.run([str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-d',
        '--disassemble='+symbol,str(elf)],capture_output=True,text=True,check=True)
    for check in checks:assert check in result.stdout,(symbol,check)
    (OUT/('compiled-'+symbol+'.txt')).write_text(result.stdout)
    rows.append(dict(symbol=symbol,required_sequences=list(checks),limit=16))
save('compiled-loop-limits.json',dict(status='PASS',dat_sha256=file_sha(DAT),elf_sha256=file_sha(elf),loops=rows,
    scope='Two loop counter sequences only. Native bounded-moves tests verify the return after sixteen transactions.'))
print('PASS two compiled loop counters',flush=True)
