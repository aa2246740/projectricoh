#!/usr/bin/python3 -I
"""Rebuild the resident into the declared temporary directory."""
from pathlib import Path
import importlib.util
import json
import os
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from static_check import Elf, sha

source = ROOT / 'firmware/resident_v39/resident/build.py'
spec = importlib.util.spec_from_file_location('review_resident_build', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.LOCAL = Path(os.environ['REVIEW_TEMP']) / 'resident'
sys.argv = [str(source)]
assert module.main() == 0
rebuilt = Elf(module.LOCAL / 'build/resident.elf')
original = Elf(ROOT / 'firmware/resident_v39/local/resident/build/resident.elf')
assert rebuilt.sections['.resident']['data'] == original.sections['.resident']['data']
assert rebuilt.sections['.root_pins']['data'] == original.sections['.root_pins']['data']
result = json.loads((module.LOCAL / 'size.json').read_text())
result['resident_bytes_equal'] = True
result['elf_bytes_equal'] = rebuilt.raw == original.raw
result['rebuilt_trust'] = json.loads((module.LOCAL / 'trust.json').read_text())
out = ROOT / 'research/review_body_v39/evidence/build.json'
out.write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps({'resident_bytes_equal': True, 'elf_bytes_equal': result['elf_bytes_equal'],
                  'resident_sha256': sha(rebuilt.sections['.resident']['data'])}))
