"""Freeze reviewed inputs and copy the recipe build sources for generation 120."""
from pathlib import Path
import json
import shutil
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, save, load, file_sha, sha

def snapshot():
    roots = [ROOT / 'firmware' / n for n in (
        'engine_v38_b36', 'engine_v39_ux', 'engine_v40_ux', 'resident_v36',
        'image_v36', 'package_v36_g117', 'package_v36_g118', 'package_v36_g119')]
    roots += [ROOT / 'research' / n for n in (
        'ux_preview_dot_r2', 'review_g119b', 'review_g118',
        'review_g117_codegen', 'review_g117_codegen_r2')]
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
    assert not TREE.exists() and not (OUT / 'inputs-before.json').exists()
    save('inputs-before.json', snapshot())
    checks = []
    for directory in ('review_g119b', 'ux_preview_dot_r2', 'review_g117_codegen_r2'):
        manifest = ROOT / 'research' / directory / 'SHA256SUMS'
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
        body = [z.read(i) for i in z.infolist() if Path(i.filename).name == 'ilaunch3' and not i.filename.startswith('__MACOSX/')]
        assert len(body) == 1 and sha(body[0]) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    save('input-manifests.json', dict(status='PASS', checks=checks, official_body_sha256=sha(body[0])))
    words = load(ROOT / 'research/review_g119b/neutral_terms.py', 'quality_terms')
    old = ROOT / 'firmware/engine_v40_ux'
    copied = []
    for p in sorted(old.rglob('*')):
        rel = p.relative_to(old)
        if not p.is_file() or 'local' in rel.parts or '__pycache__' in rel.parts or p.name.endswith('SHA256SUMS'):
            continue
        target = TREE / words.replace(str(rel))
        target.parent.mkdir(parents=True, exist_ok=True)
        data = p.read_bytes()
        try:
            text = data.decode()
        except UnicodeDecodeError:
            target.write_bytes(data)
        else:
            target.write_text(words.replace(text.replace('engine_v40_ux', 'engine_v41_ux')))
        copied.append(dict(source_hex=str(p.relative_to(ROOT)).encode().hex(), destination=str(target.relative_to(TREE)), original=file_sha(p)))
    helper = Path('candidate/local/v34c-host/expand')
    (TREE / helper).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(old / helper, TREE / helper)
    build = TREE / 'candidate/build120.py'
    build.write_text((TREE / 'candidate/build119.py').read_text().replace('119', '120'))
    save('source-copy.json', dict(source='firmware/engine_v40_ux', destination='firmware/engine_v41_ux', copied=copied,
                                  inherited_local_results=False, readonly_helper=str(helper)))
    print('PASS input manifests and official archive; copied sources', len(copied), flush=True)

if __name__ == '__main__':
    main()
