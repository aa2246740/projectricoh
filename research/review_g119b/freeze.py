"""Freeze the named review inputs, verify author manifest without trusting results."""
from pathlib import Path
import json
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, ROOT, save, file_sha, sha

def main():
    roots = [ROOT / 'firmware' / n for n in (
        'engine_v38_b36', 'engine_v39_ux', 'engine_v40_ux',
        'package_v36_g117', 'package_v36_g118', 'package_v36_g119')]
    roots += [ROOT / 'research' / n for n in (
        'ux_preview_dot_r2', 'review_g118', 'review_g117_container',
        'review_g117_codegen', 'review_g117_codegen_r2', 'review_v36_body',
        't_persistence', 't_recovery')]
    roots += [ROOT / 'artifacts/downloads/gxr-151.zip']
    paths = set()
    for root in roots:
        for p in ([root] if root.is_file() else root.rglob('*')):
            if p.is_file(): paths.add(p)
    paths.update((ROOT / 'research/review_g119').glob('*.py'))
    manifest = ROOT / 'research/ux_preview_dot_r2/SHA256SUMS'
    checks = []
    for line in manifest.read_text().splitlines():
        expected, name = line.split('  ', 1)
        p = (manifest.parent / name).resolve()
        actual = file_sha(p)
        checks.append(dict(path_hex=str(p.relative_to(ROOT)).encode().hex(), expected=expected, actual=actual, ok=expected==actual))
        paths.add(p)
    save('author-manifest-check.json', dict(total=len(checks), ok=sum(x['ok'] for x in checks), checks=checks))
    assert all(x['ok'] for x in checks)
    snapshot = {str(p.relative_to(ROOT)).encode().hex():dict(bytes=p.stat().st_size,sha256=file_sha(p)) for p in sorted(paths)}
    target = OUT / ('inputs-after.json' if '--after' in sys.argv else 'inputs-before.json')
    save(target.name, snapshot)
    archive = ROOT / 'artifacts/downloads/gxr-151.zip'
    assert file_sha(archive)=='3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
    with zipfile.ZipFile(archive) as z:
        official = [z.read(x) for x in z.namelist() if Path(x).name=='ilaunch3' and not x.startswith('__MACOSX/')]
        assert len(official)==1 and sha(official[0])=='da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    if '--after' in sys.argv:
        before=json.loads((OUT/'inputs-before.json').read_text())
        changed=[n for n in set(before)|set(snapshot) if before.get(n)!=snapshot.get(n)]
        save('input-integrity.json',dict(files=len(snapshot),changed=changed,ok=not changed))
        assert not changed,changed
    print('PASS author manifest',len(checks),'/',len(checks),'input files',len(snapshot),'official ilaunch3 da1980e9',flush=True)

if __name__=='__main__': main()
