"""Freeze upstream source once; never overwrite this task's edited copies."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime import HERE, ROOT, LOCAL, SRC, guard, sha

def main():
    guard()
    manifest = HERE / 'UPSTREAM.json'
    if manifest.exists():
        raise SystemExit('Source snapshot already exists; do not overwrite edits.')
    paths = []
    for directory in ('firmware/engine/core', 'firmware/engine/panel', 'firmware/card_container_v2', 'firmware/resident_slim'):
        paths += [p for p in (ROOT / directory).rglob('*') if p.is_file() and 'local' not in p.relative_to(ROOT / directory).parts and p.suffix in ('.c', '.h', '.S', '.ld')]
    paths += [ROOT / p for p in ('firmware/resident_v2/abi.h', 'firmware/card_container/gxrce.h', 'research/recipe_tweak/r2/tweak_int.c', 'research/recipe_tweak/r2/tweak_int.h')]
    evidence = []
    for source in sorted(paths):
        rel = source.relative_to(ROOT)
        target = SRC / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha(source)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target) == before, 'source changed during freeze'
        evidence.append({'source': str(rel), 'copy': str(target.relative_to(HERE)), 'sha256': before})
    for name, source in [('pack_v1.py', ROOT / 'firmware/card_container/pack.py'), ('pack.py', ROOT / 'firmware/card_container_v2/pack.py')]:
        shutil.copyfile(source, HERE / name)
        evidence.append({'source': str(source.relative_to(ROOT)), 'copy': name, 'sha256': sha(source)})
    manifest.write_text(json.dumps(evidence, indent=2) + '\n')
    print(f'Frozen {len(evidence)} source files inside integrated/.')

if __name__ == '__main__':
    main()
