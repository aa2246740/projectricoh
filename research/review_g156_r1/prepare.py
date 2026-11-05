"""Freeze exact inputs and prepare private copies for the cold-start sample."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
C.setup()

paths = set()
for folder in [*C.PACKAGES.values(), C.BASE, C.ENGINE, C.ORIGINAL,
               C.ROOT/'tools/gxr_emulator_fast/strict_r3',
               C.ROOT/'tools/gxr_emulator_fast/strict_r2']:
    for p in folder.rglob('*'):
        if p.is_file() and not p.is_symlink() and p.suffix != '.pyc':
            rel = p.relative_to(folder)
            if folder in (C.BASE, C.ENGINE) and 'local' in rel.parts:
                if p.name not in ('engine.elf','engine.bin','reloc.bin'):
                    continue
            if folder == C.ORIGINAL and 'local' in rel.parts:
                if p.suffix not in ('.json','.bin','.py') and 'inputs' not in rel.parts:
                    continue
            paths.add(p)
for rel in ['firmware/image_v310/local/ilaunch3',
            'firmware/resident_v310_g155/local/resident/resident.bin',
            'firmware/resident_v310_g155/local/resident/trust.json',
            'firmware/resident_v310_g155/local/resident/symbols.log',
            'research/recipe_redo_r1/candidate_registry.json',
            'research/recipe_redo_r1/capacity_safe_profile.json',
            'research/recipe_redo_r1/REPORT.md',
            'research/review_g155c_r1/REVIEW.md',
            'studio/src/gxr_studio/camdata/datcodec.py',
            'research/v39_g153/dat_format.py']:
    p=C.ROOT/rel
    if p.is_file(): paths.add(p)
rows=[]
for p in sorted(paths):
    rows.append(dict(path=str(p.relative_to(C.ROOT)),size=p.stat().st_size,sha256=C.sha(p.read_bytes())))
C.save(C.HERE/'evidence/frozen_inputs.json',dict(files=rows,status='FROZEN'))
for name in ['r2-maps-release.json','r2-maps-test.json']:
    (C.HERE/'evidence'/name).write_bytes((C.ORIGINAL/'evidence'/name).read_bytes())
(C.LOCAL/'structure-offsets.json').write_bytes((C.ORIGINAL/'local/structure-offsets.json').read_bytes())
registry=json.loads((C.RECORDS/'candidate_registry.json').read_text())
source=C.ORIGINAL/'local/inputs/research/recipe_redo_r1'
dest=C.LOCAL/'inputs/research/recipe_redo_r1'
for rel in ['candidate_registry.json','capacity_safe_profile.json'] + [r['record_file'] for r in registry['profiles'] if r.get('record_file')]:
    p=source/rel
    if p.is_file():
        q=dest/rel
        q.parent.mkdir(parents=True,exist_ok=True)
        q.write_bytes(p.read_bytes())
print(json.dumps(dict(status='PASS',frozen_files=len(rows))))
