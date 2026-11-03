"""重建新目录与测试包，检查关键交付文件逐字节可重复。"""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *


def snapshot():
    paths = [PACKAGE / 'MANIFEST.json', PACKAGE / 'local/SD_ROOT/GXRCE.DAT']
    paths += [PACKAGE / 'local/build' / name for name in
              ('engine.elf', 'engine.bin', 'reloc.bin', 'layout.json', 'trust.bin', 'release-zero-users.DAT')]
    paths += [p for p in ENGINE.rglob('*') if p.is_file() and 'local' not in p.relative_to(ENGINE).parts]
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}


def main():
    guard()
    before = snapshot()
    started = time.monotonic()
    for name in ('prepare', 'build'):
        load(HERE / (name + '.py'), 'g154_looks_reproduce_' + name).main()
    after = snapshot()
    assert before == after, [name for name in before if before[name] != after.get(name)]
    save(HERE / 'evidence/reproduce.json', dict(status='PASS', compared=len(before),
         seconds=time.monotonic() - started, files=after))
    print(json.dumps(dict(status='PASS', compared=len(before), dat_sha256=sha((PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()))))


if __name__ == '__main__':
    main()
