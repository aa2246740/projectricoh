"""Retain the exact native draw prefix and summarize late stores in both versions."""
from pathlib import Path
from collections import Counter
import importlib.util
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_draw_image',ROOT/'tools/native_harness/image_loader.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
body=m.Image(ROOT/'firmware/image_v36/local/package/SD_ROOT/ilaunch3','50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008')
prefix=OUT/'local/native-draw-prefix.bin';prefix.write_bytes(body.bytes_at(0x201fd360,0x200))
tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
argv=[str(tool),'-D','-EB','-b','binary','-m','m32r','--adjust-vma=0x201fd360',str(prefix)]
result=subprocess.run(argv,check=True,capture_output=True,text=True)
(OUT/'local/native-draw-prefix.disasm').write_text(result.stdout)
rows=[]
for path in sorted((OUT/'local/window-consequences').glob('*.json')):
    r=json.loads(path.read_text());stores=r['all_CPU_stores_after_switch']
    native=[x for x in stores if 0x20000000<=int(x['pc'],16)<0x20400000 and 0x20000000<=int(x['address'],16)<0x20600000]
    body_stores=[x for x in native if int(x['pc'],16)>=0x20060000]
    rows.append(dict(case=r['case'],generation=r['generation'],panel=r['panel'],switch=r['switch_kind'],
        late_watched_UI=len(r['late_watched_UI']),late_S=len(r['late_S']),late_Image_setters=len([x for x in r['setters'] if x['after_switch']]),
        late_native_body_static_stores=[dict(pc=x['pc'],address=x['address'],bytes=x['size'],value=int(x['data'],16)) for x in body_stores],
        old_row_visits=sum(x['after_switch'] for x in r['painted']),file_mutations=r['file_mutations']))
(OUT/'evidence/native-draw-consequences.json').write_text(json.dumps(dict(cases=rows,disassembler_command=argv,
    scope='All modeled CPU stores after the switch; graphics device leaf functions remain modeled.'),indent=2)+'\n')
print(json.dumps(rows,indent=2))
