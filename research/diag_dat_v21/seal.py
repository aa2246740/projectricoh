"""Seal the task outputs and verify the saved hashes without changing inputs."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope


def main():
    scope.freeze_check()
    sums = scope.HERE / 'SHA256SUMS'
    if '--check' not in sys.argv:
        paths = [scope.ROOT / p for p in json.loads((scope.HERE / 'local/inputs-before.json').read_text())]
        for directory in scope.OUTPUTS:
            for path in directory.rglob('*'):
                rel = path.relative_to(directory)
                if path == sums or not path.is_file() or '__pycache__' in rel.parts:
                    continue
                if 'tmp' in rel.parts or 'modules' in rel.parts:
                    continue
                assert not path.is_symlink()
                paths.append(path)
        sums.write_text(''.join(scope.sha(p) + '  ' + str(p.relative_to(scope.ROOT)) + '\n'
                               for p in sorted(set(paths))))
    lines = sums.read_text().splitlines()
    for line in lines:
        digest, name = line.split(None, 1)
        assert scope.sha(scope.ROOT / name) == digest, name
    print('SHA256SUMS RETURN 0 COUNT', len(lines))


if __name__ == '__main__':
    main()
