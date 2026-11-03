"""Record read-only replay dependencies beyond the initial protected roots."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, save, file_sha

paths = ['research/review_g117_codegen/audit.py',
         'research/emulator_feasibility_r1/prototype/boot_probe.py',
         'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
         'research/three_module_audit_r1/local/name_widths.json',
         'research/firmware/ilaunch3-sections.csv',
         'firmware/engine_v40_ux/candidate/local/full-r13/engine.elf',
         'firmware/engine_v38_b36/candidate/local/full-r13/engine.elf',
         'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT',
         'firmware/engine_v36_r28/candidate/local/full-r13/trust.bin',
         'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT']
paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'artifacts/firmware/gxr-1.51').glob('*')) if p.is_file()]
rows = [dict(path_hex=name.encode().hex(), bytes=(ROOT/name).stat().st_size,
             sha256=file_sha(ROOT/name)) for name in paths]
save('extra-inputs-before.json', dict(count=len(rows), files=rows))
print('PASS additional dependencies', len(rows), flush=True)
