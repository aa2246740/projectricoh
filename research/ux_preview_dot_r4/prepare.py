"""Check frozen inputs before native quality checks."""
from pathlib import Path
import json
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, PACKAGE, save, load, file_sha, sha

def snapshot():
    groups = {
        'firmware': ('engine_v38_b36', 'engine_v39_ux', 'engine_v40_ux',
                     'engine_v41_ux', 'resident_v36', 'image_v36',
                     'package_v36_g117', 'package_v36_g118',
                     'package_v36_g119', 'package_v36_g120'),
        'research': ('ux_preview_dot_r2', 'ux_preview_dot_r3', 'review_g119b',
                     'review_g119', 'review_g118', 'review_g117_codegen',
                     'review_g117_codegen_r2'),
    }
    roots = [ROOT / group / name for group, names in groups.items() for name in names]
    roots += [ROOT / 'tools/native_harness', ROOT / 'artifacts/downloads/gxr-151.zip']
    files = set()
    for root in roots:
        files.update(p for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file())
    return {str(p.relative_to(ROOT)).encode().hex(): dict(bytes=p.stat().st_size, sha256=file_sha(p))
            for p in sorted(files)}

def main():
    if '--after' in sys.argv:
        before = json.loads((OUT / 'inputs-before.json').read_text())
        after = snapshot()
        changed = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
        save('inputs-after.json', after)
        save('input-integrity.json', dict(status='PASS' if not changed else 'FAIL', files=len(before), changed=changed))
        assert not changed
        print('PASS protected inputs unchanged', len(before), flush=True)
        return
    assert not TREE.exists() and not PACKAGE.exists()
    save('inputs-before.json', snapshot())
    checks = []
    for group, directory, manifest_name in (
        ('research', 'ux_preview_dot_r3', 'SHA256SUMS'),
        ('research', 'review_g119b', 'SHA256SUMS'),
        ('research', 'review_g117_codegen_r2', 'SHA256SUMS'),
        ('firmware', 'engine_v41_ux', 'EVIDENCE_SHA256SUMS'),
        ('firmware', 'package_v36_g120', 'SHA256SUMS'),
    ):
        manifest = ROOT / group / directory / manifest_name
        bad = []
        lines = manifest.read_text().splitlines()
        for line in lines:
            expected, name = line.split('  ', 1)
            path = (manifest.parent / name).resolve()
            assert path.is_relative_to(manifest.parent)
            if file_sha(path) != expected:
                bad.append(name.encode().hex())
        checks.append(dict(directory=directory, manifest_sha256=file_sha(manifest), files=len(lines), failed=bad))
        assert not bad, directory
    archive = ROOT / 'artifacts/downloads/gxr-151.zip'
    assert file_sha(archive) == '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
    with zipfile.ZipFile(archive) as z:
        bodies = [z.read(i) for i in z.infolist() if Path(i.filename).name == 'ilaunch3' and not i.filename.startswith('__MACOSX/')]
        assert len(bodies) == 1 and sha(bodies[0]) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    save('input-manifests.json', dict(status='PASS', checks=checks, official_body_sha256=sha(bodies[0])))
    words = load(ROOT / 'research/review_g119b/neutral_terms.py', 'quality_terms')
    source = ROOT / 'research/ux_preview_dot_r3/native_ux.py'
    text = words.replace(source.read_text().replace('engine_v41_ux', 'engine_v40_ux'))
    (OUT / 'native_ux.py').write_text(text)
    layout = ROOT / 'research/ux_preview_dot_r3/local/layout/layout.json'
    target = OUT / 'local/layout/layout.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(layout.read_bytes())
    save('harness-provenance.json', dict(source=str(source.relative_to(ROOT)), source_sha256=file_sha(source),
        copied_sha256=file_sha(OUT/'native_ux.py'), transformation='Redirect source tree from 41 to the frozen gen119 tree 40; native functions unchanged.',
        layout_sha256=file_sha(layout), inherited_test_results=False))
    print('PASS input manifests and official archive; native source ready', flush=True)

if __name__ == '__main__':
    main()
