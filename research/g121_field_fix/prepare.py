"""Record immutable inputs and prepare the generation 121 working copy."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/g121_field_fix'
TREE = ROOT / 'firmware/engine_v43_fix'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    pins = json.loads((ROOT / 'research/review_g120b/official-input-pins.json').read_text())['pins']
    for name, expected in pins.items():
        assert digest(ROOT / name) == expected, name
    with zipfile.ZipFile(ROOT / 'artifacts/downloads/gxr-151.zip') as archive:
        members = [n for n in archive.namelist() if Path(n).name == 'ilaunch3' and not n.startswith('__MACOSX/')]
        assert len(members) == 1
        assert hashlib.sha256(archive.read(members[0])).hexdigest() == pins['artifacts/firmware/gxr-1.51/ilaunch3']
    roots = ['firmware/engine_v42_ux', 'firmware/package_v36_g120b', 'firmware/resident_v36',
             'firmware/image_v36', 'research/review_g120b', 'research/review_g120b_codegen',
             'research/tweak_panel_ui', 'research/ux_preview_dot_r5', 'tools/native_harness']
    paths = {ROOT / name for name in pins}
    for name in roots:
        paths.update(p for p in (ROOT / name).rglob('*') if p.is_file())
    rows = [dict(path_hex=str(p.relative_to(ROOT)).encode().hex(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(paths)]
    (OUT / 'inputs-before.json').write_text(json.dumps(dict(roots=roots, pins=pins, files=rows), indent=2) + '\n')
    assert not TREE.exists(), TREE
    shutil.copytree(ROOT / 'firmware/engine_v42_ux', TREE)
    changed = []
    for p in TREE.rglob('*'):
        if p.is_file() and p.suffix in ('.py', '.h', '.c', '.md', '.sh'):
            text = p.read_text()
            routed = text.replace('engine_v42_ux', 'engine_v43_fix')
            if routed != text:
                p.write_text(routed)
                changed.append(str(p.relative_to(ROOT)))
    names = ('native_ux run_native native_exits native_cases fn2_quality fn2_all confirm_paths '
             'concurrent_menu ui_trace_scope ui_cutpoints entry_switch failure_boundaries '
             'coalescing latch_paths native_names h07_native_finish runtime_guard run_remaining').split()
    for name in names:
        p = ROOT / 'research/review_g120b' / (name + '.py')
        text = p.read_text().replace('engine_v42_ux', 'engine_v43_fix').replace('package_v36_g120b', 'package_v36_g121')
        text = text.replace('==120', '==121').replace('== 120', '== 121').replace('generation=120', 'generation=121')
        (OUT / p.name).write_text(text)
    shutil.copytree(ROOT / 'research/review_g120b/local/layout', OUT / 'local/layout')
    (OUT / 'preparation.json').write_text(json.dumps(dict(status='PASS', protected_files=len(rows), routed_sources=changed), indent=2) + '\n')
    print('PASS input identities and working copy', len(rows), flush=True)

if __name__ == '__main__':
    main()
