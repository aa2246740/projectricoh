"""Preserve one A compile/link iteration without overwriting earlier evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPORT = ROOT / 'research/body_v4_w0'


def main(name):
    assert name and all(c.isalnum() or c in '-_' for c in name)
    target = HERE / 'local/a-iterations' / name
    assert not target.exists(), 'iteration already preserved'
    files = [p for p in HERE.iterdir() if p.is_file()]
    files += [p for p in (HERE / 'generated').iterdir() if p.is_file()]
    files += [HERE / 'local' / n for n in ('resident.elf', 'resident.map', 'resident-strict.map',
              'strict-link.log', 'resident-host-machine.elf', 'disassembly.log', 'linked_hooks.S',
              'hook_metadata.c', 'trust.c', 'budget.S', 'commands.json')]
    files += list((HERE / 'local/objects').glob('*'))
    manifest = {}
    for path in files:
        destination = target / path.relative_to(HERE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        manifest[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (target / 'input-sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
    output = REPORT / 'local/a-iterations' / name
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(REPORT / 'size.json', output / 'size.json')
    print(name, json.loads((output / 'size.json').read_text())['payload_bytes'])


if __name__ == '__main__':
    main(sys.argv[1])
