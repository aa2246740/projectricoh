"""Retain the pre-mode-fix artifacts before rebuilding the candidate."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    dest = HERE / 'local/p1-before'
    dest.mkdir(exist_ok=False)
    rows = {}
    for profile in ('boot-on', 'boot-off', 'release-auto', 'full-r13'):
        src = ROOT / 'firmware/engine_v67_g155c/candidate/local' / profile
        shutil.copytree(src, dest / profile)
    for name in ('package_v310_g155c', 'package_v310_g155c_test'):
        shutil.copytree(ROOT / 'firmware' / name, dest / name)
    shutil.copytree(ROOT / 'firmware/engine_v67_g155c/candidate/containers/product', dest / 'product',
                    ignore=shutil.ignore_patterns('local', '__pycache__'))
    for name in ('artifact-audit.json', 'source-differences.json', 'source-differences.patch',
                 'build-on.json', 'build-off.json', 'build-release-auto.json', 'parent-code-comparison.json'):
        src = HERE / 'evidence' / name
        if src.exists():
            shutil.copyfile(src, dest / name)
    for path in sorted(dest.rglob('*')):
        if path.is_file():
            rows[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = dict(status='RETAINED_BASELINE', files=rows,
        interrupted_case='finalrelease-cold1', interrupted_run_is_result=False,
        reason='The added mode contract and release BOOT policy require a new artifact hash.',
        deadline_utc='2026-11-03T07:28:28Z')
    (HERE / 'evidence/p1-before-archive.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(files=len(rows), destination=str(dest))))


if __name__ == '__main__':
    main()
