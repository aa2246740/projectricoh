"""Record fixed inputs and prepare the three generation 122 output roots."""
from pathlib import Path
import hashlib
import json
import plistlib
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/g122_keep_list'
TREE = ROOT / 'firmware/engine_v44_keep'
PACKAGE = ROOT / 'firmware/package_v36_g122'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType'] == 'apfs' and volume['WritableVolume']
    pins = json.loads((ROOT / 'research/review_g120b/official-input-pins.json').read_text())['pins']
    pins['firmware/package_v36_g121/SD_ROOT/GXRCE.DAT'] = '3b9342ee28c523d7737e320abac1cc37ee3e6c6d122a72d5fe90cd2a3f2ee131'
    for name, expected in pins.items():
        assert digest(ROOT / name) == expected, name
    with zipfile.ZipFile(ROOT / 'artifacts/downloads/gxr-151.zip') as archive:
        names = [s for s in archive.namelist() if Path(s).name == 'ilaunch3' and not s.startswith('__MACOSX/')]
        assert len(names) == 1
        assert hashlib.sha256(archive.read(names[0])).hexdigest() == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    roots = ('firmware/engine_v43_fix', 'firmware/package_v36_g120b',
             'firmware/package_v36_g121', 'firmware/resident_v36', 'firmware/image_v36',
             'research/g121_field_fix', 'research/review_g120b', 'tools/native_harness')
    paths = {ROOT / name for name in pins}
    for name in roots:
        paths.update(p for p in (ROOT / name).rglob('*') if p.is_file())
    rows = [dict(path_hex=str(p.relative_to(ROOT)).encode().hex(), bytes=p.stat().st_size,
                 sha256=digest(p)) for p in sorted(paths)]
    (OUT / 'inputs-before.json').write_text(json.dumps(dict(roots=roots, pins=pins, files=rows), indent=2) + '\n')
    assert not TREE.exists() and not PACKAGE.exists()
    shutil.copytree(ROOT / 'firmware/engine_v43_fix', TREE)
    routed = []
    for p in TREE.rglob('*'):
        if p.is_file() and p.suffix in ('.py', '.c', '.h', '.md', '.sh', '.txt'):
            original = p.read_text()
            updated = original.replace('engine_v43_fix', 'engine_v44_keep')
            if updated != original:
                p.write_text(updated)
                routed.append(str(p.relative_to(TREE)))
    names = ('native_ux run_native native_exits native_cases fn2_quality fn2_all confirm_paths '
             'concurrent_menu ui_trace_scope ui_cutpoints entry_switch failure_boundaries '
             'coalescing latch_paths native_names h07_native_finish runtime_guard run_remaining '
             'common run_queue field_cases native_sequence recovery_cases settings_cases '
             'allocation_cases bounded_moves notice_cases list_counts machine_gates storage_check '
             'critical_codegen seal').split()
    for name in names:
        original = (ROOT / 'research/g121_field_fix' / (name + '.py')).read_text()
        updated = original.replace('engine_v43_fix', 'engine_v44_keep').replace('package_v36_g121', 'package_v36_g122')
        updated = updated.replace('g121_field_fix', 'g122_keep_list').replace('Generation 121', 'Generation 122')
        updated = updated.replace('==121', '==122').replace('== 121', '== 122').replace('generation=121', 'generation=122')
        if name == 'coalescing':
            updated = updated.replace("'121'", "'122'")
        if name == 'run_queue':
            updated = updated.replace("'coalescing.py', '121'", "'coalescing.py', '122'")
        if name == 'common':
            updated = updated.replace('2026-10-28T00:44:36Z', '2026-10-28T03:51:22Z').replace('2026-10-28T03:44:36Z', '2026-10-28T06:51:22Z')
        (OUT / (name + '.py')).write_text(updated)
    shutil.copytree(ROOT / 'research/g121_field_fix/local/layout', OUT / 'local/layout')
    build = (TREE / 'candidate/build121.py').read_text().replace('121', '122')
    (TREE / 'candidate/build122.py').write_text(build)
    PACKAGE.mkdir()
    shutil.copytree(ROOT / 'firmware/package_v36_g120b/SD_ROOT', PACKAGE / 'SD_ROOT',
                    ignore=shutil.ignore_patterns('GXRCE.DAT'))
    (OUT / 'preparation.json').write_text(json.dumps(dict(status='PASS', protected_files=len(rows),
        routed_sources=routed, card_fixed_files=len(list((PACKAGE / 'SD_ROOT').iterdir()))), indent=2) + '\n')
    print('PASS fixed inputs, source copy and card files', len(rows), flush=True)

if __name__ == '__main__':
    main()
