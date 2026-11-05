"""Inspect real compiler output after an over-limit link, without changing gates."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('measure-linked-code')
out=C.ENGINE/'candidate/local/product-r13/m32r-lto-oz';obj=C.LOCAL/'probe-code.o'
C.run([C.GCC,'-m32r','-c',out/'probe.elf.ltrans0.ltrans.s','-o',obj],'measure-code-assemble')
E=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g157_code_sizes').Elf
old=E(C.BASE/'candidate/local/boot-on/engine.elf');new=E(obj)
rows=[]
for n,s in new.symbols.items():
    if s['info']&15!=2:continue
    o=old.symbols.get(n,{}).get('size',0)
    rows.append(dict(name=n,old=o,new=s['size'],delta=s['size']-o))
rows.sort(key=lambda r:-r['delta'])
C.save(C.LOCAL/'code-size-delta.json',rows)
print(json.dumps(rows[:45],indent=2))
