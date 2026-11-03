"""Protect the shared read-only interpreter, body and baseline fixture helpers."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save,file_sha

paths=set((ROOT/'tools/native_harness').glob('*.py'))
paths.update((ROOT/'firmware/resident_v36/resident').glob('*'))
paths.update(ROOT/p for p in (
 'firmware/image_v36/local/package/SD_ROOT/ilaunch3',
 'firmware/resident_v36/local/resident/build/resident.elf',
 'firmware/engine_v40_ux/candidate/local/v34c-host/expand',
 'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT',
 'firmware/engine_v36_r28/candidate/local/full-r13/trust.bin',
 'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT',
 'research/emulator_feasibility_r1/prototype/boot_probe.py',
 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'))
snapshot={str(p.relative_to(ROOT)).encode().hex():dict(bytes=p.stat().st_size,sha256=file_sha(p)) for p in sorted(paths) if p.is_file()}
if '--after' in sys.argv:
    before=json.loads((OUT/'runtime-inputs-before.json').read_text())
    changes=[p for p in set(before)|set(snapshot) if before.get(p)!=snapshot.get(p)]
    save('runtime-input-integrity.json',dict(files=len(snapshot),changed=changes,ok=not changes))
    save('runtime-inputs-after.json',snapshot)
    assert not changes,changes
else:
    assert not (OUT/'runtime-inputs-before.json').exists()
    save('runtime-inputs-before.json',snapshot)
print('PASS shared runtime snapshot',len(snapshot),flush=True)
