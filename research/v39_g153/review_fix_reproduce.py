"""Reproduce the selected source and DAT without changing the tested bytes."""
from pathlib import Path
import hashlib
import json
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINE = ROOT / 'firmware/engine_v62_g153'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {str(path.relative_to(ENGINE)): sha(path)
            for path in sorted(ENGINE.rglob('*'))
            if path.is_file() and 'local' not in path.relative_to(ENGINE).parts}


def main():
    before_sources = sources()
    built = ENGINE / 'candidate/local/full-r13'
    names = ['GXRCE.DAT', 'engine.elf', 'engine.bin', 'relocs.bin', 'layout.json']
    names = [name for name in names if (built / name).is_file()]
    before_artifacts = {name: sha(built / name) for name in names}
    for script, args in (('port.py', []), ('build.py', ['dat'])):
        sys.argv = [str(HERE / script), *args]
        runpy.run_path(str(HERE / script), run_name='__main__')
    assert sources() == before_sources
    after_artifacts = {name: sha(built / name) for name in names}
    assert after_artifacts == before_artifacts
    result = dict(status='PASS', unchanged_source_files=len(before_sources),
                  reproduced_artifacts=after_artifacts, resident_rebuilt=False)
    (HERE / 'review_fix/evidence/reproduce.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
