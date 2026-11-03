"""Validate preserved label and layout evidence without copying old harness text."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,load,save,sha

audit=load(ROOT/'research/review_g117_codegen/audit.py','setup_elf')
rows=[]
for gen,tree in ((118,'engine_v39_ux'),(119,'engine_v40_ux')):
    labelled=audit.Elf(OUT/f'labels{gen}/engine.elf')
    final=audit.Elf(ROOT/f'firmware/{tree}/candidate/local/full-r13/engine.elf')
    assert labelled.engine['data']==final.engine['data']
    rows.append(dict(generation=gen,label_elf=sha(labelled.raw),final_engine=sha(final.engine['data']),engine_bytes_equal=True))
for name in ('layout','adapter-layout'):
    assert json.loads((OUT/'local/layout'/(name+'.json')).read_text())
save('setup-validation.json',dict(status='PASS',labels=rows,source_copy=False,build=False))
print('PASS preserved label/layout evidence; no source copies or build',flush=True)
