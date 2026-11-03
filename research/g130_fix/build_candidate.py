#!/usr/bin/python3
"""Build generation 130 and check its complete card directory."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g130_fix'
ENGINE = ROOT / 'firmware/engine_v50_h07'
PACKAGE = ROOT / 'firmware/package_v36_g130'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    import sys
    sys.path.insert(0, str(ENGINE / 'candidate'))
    import common
    original = common.run
    def run(arguments, label, **options):
        options['timeout'] = max(options.get('timeout', 120), 1200)
        return original(arguments, label, **options)
    common.run = run
    sys.argv = [str(ENGINE / 'candidate/build130.py')]
    runpy.run_path(sys.argv[0], run_name='__main__')
    full = ENGINE / 'candidate/local/full-r13'
    raw = (full / 'GXRCE.DAT').read_bytes()
    assert int.from_bytes(raw[28:32], 'big') == 130
    shutil.copyfile(full / 'GXRCE.DAT', PACKAGE / 'local/SD_ROOT/GXRCE.DAT')
    fixed = []
    for path in sorted((ROOT / 'firmware/package_v36_g120b/SD_ROOT').rglob('*')):
        if not path.is_file() or path.name == 'GXRCE.DAT':
            continue
        relative = path.relative_to(ROOT / 'firmware/package_v36_g120b/SD_ROOT')
        assert path.read_bytes() == (PACKAGE / 'local/SD_ROOT' / relative).read_bytes()
        fixed.append(str(relative))
    files = sorted(p for p in (PACKAGE / 'local/SD_ROOT').rglob('*') if p.is_file())
    assert len(fixed) == 29 and len(files) == 30
    assert (full / 'effective-rows.bin').read_bytes() == (ROOT / 'firmware/engine_v48_own/candidate/local/full-r13/effective-rows.bin').read_bytes()
    result = dict(generation=130, dat_sha256=sha(PACKAGE / 'local/SD_ROOT/GXRCE.DAT'),
                  files=30, fixed_files_equal_g120b=fixed, file_bytes=len(raw),
                  effective_rows_equal_g127=True, elf_sha256=sha(full / 'engine.elf'),
                  engine_sha256=sha(full / 'engine.bin'))
    (WORK / 'evidence/package.json').write_text(json.dumps(result, indent=2) + '\n')
    (PACKAGE / 'CARD_SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(PACKAGE / 'local/SD_ROOT')) + '\n' for p in files))
    print(json.dumps(dict(name='build-package', returncode=0, files=30, generation=130)), flush=True)

if __name__ == '__main__':
    main()
