"""清理误选旧驱动时由本轮四个 PID 新建的目录，不动其父目录。"""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *


def main():
    previous_path = HERE / 'evidence/misbound-cleanup.json'
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    names = ('final-sizes-c', 'sizes-python-confirm', 'sizes-observe-c', 'size-probe-c')
    rows = []
    for name in names:
        receipt = json.loads((HERE / 'evidence' / ('job-' + name + '.json')).read_text())
        pid, started = receipt['pid'], receipt['started_ns'] / 1e9
        path = ROOT / f'research/v39_g153/local/native/p{pid}'
        temporary = Path(f'/Volumes/Workspace/Scratch/tmp/projectricoh/g153/native/p{pid}')
        assert not temporary.exists(), temporary
        if not path.exists():
            assert previous is not None and any(row['path'] == str(path) and row['removed'] for row in previous['directories'])
            rows.append(next(row for row in previous['directories'] if row['path'] == str(path)))
            continue
        assert not path.is_symlink() and path.parent == ROOT / 'research/v39_g153/local/native'
        birth = path.stat().st_birthtime
        assert 0 <= birth - started < 5, (path, birth, started)
        files = [p for p in sorted(path.rglob('*')) if p.is_file() and not p.is_symlink()]
        hashes = {str(p.relative_to(path)): sha(p.read_bytes()) for p in files}
        record = dict(job=name, pid=pid, path=str(path), birth_minus_start_seconds=birth - started,
            files=len(files), bytes=sum(p.stat().st_size for p in files), sha256=hashes,
            old_scratch_auto_removed=True)
        shutil.rmtree(path)
        record['removed'] = not path.exists()
        assert record['removed']
        rows.append(record)
    save(previous_path, dict(status='PASS', directories=rows,
         reason='common.py prepended the legacy directory, selecting its same-named native_support module. Only task-created PID directories removed.'))
    print(json.dumps(dict(status='PASS', removed_directories=len(rows), files=sum(row['files'] for row in rows))))


if __name__ == '__main__':
    main()
