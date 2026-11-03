"""Assemble the g139m release and test packages (copy of research/g139_fix/package.py).

- firmware/package_v38_g139m:      v3.8 body files (byte-identical to package_v38_g139 and _g137) + the g139m DAT, 0 user entries.
- firmware/package_v38_g139m_test: the same 29 body files + the g139m DAT with the g139 test package's three user
                                   entries (FCC-001, FCC*002, GRN*001), built by the g139m tree's user_entries.py.
Reads package_v38_g137 / package_v38_g139 / package_v38_g139_test (never writes them). /usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'firmware/package_v38_g137/local/SD_ROOT'
BUILT = ROOT / 'firmware/engine_v57_g139m/candidate/local/full-r13'
CLI = ROOT / 'firmware/engine_v57_g139m/candidate/user_entries.py'
G139 = ROOT / 'firmware/package_v38_g139/local/SD_ROOT'
G139_TEST = ROOT / 'firmware/package_v38_g139_test/local/SD_ROOT'
WORK = Path(__file__).resolve().parent
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
LIMIT = 106124      # 108,124 design budget minus the 2,000 B reserved for the 28mm fix
# Test entries: two in FCC (one unchanged, one with Cont +1) and the GR IV
# bleach approximation from research/gr4_bleach_fit_r1/user_entry_GR-BB.txt
# (base 02 GRN, Cont=2 High=5 Shad=5 Satu=-5; on camera GRN*001).
GR_BB = ROOT / 'research/gr4_bleach_fit_r1/user_entry_GR-BB.txt'
MANIFEST = '5\n5 Cont=1\n' + GR_BB.read_text()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assemble(target_dir, dat_bytes):
    target = target_dir / 'local/SD_ROOT'
    target.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in SOURCE.iterdir() if p.is_file())
    assert len(files) == 30 and sha(SOURCE / 'ilaunch3') == BODY_SHA
    for path in files:
        if path.name != 'GXRCE.DAT':
            shutil.copyfile(path, target / path.name)
    (target / 'GXRCE.DAT').write_bytes(dat_bytes)
    out = sorted(p for p in target.iterdir() if p.is_file())
    assert [p.name for p in out] == [p.name for p in files]
    same = [p.name for p in out if p.name != 'GXRCE.DAT' and (SOURCE / p.name).read_bytes() == p.read_bytes()]
    assert len(same) == 29 and sha(target / 'ilaunch3') == BODY_SHA
    same139 = [p.name for p in out if p.name != 'GXRCE.DAT' and (G139 / p.name).read_bytes() == p.read_bytes()]
    assert len(same139) == 29
    link = target_dir / 'SD_ROOT'
    if not link.is_symlink():
        link.symlink_to('local/SD_ROOT')
    (target_dir / '.gitignore').write_text('local/\nSD_ROOT\n')
    (target_dir / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in out))
    return dict(files=len(out), unchanged_from_v38_g137=len(same), unchanged_from_v38_g139=len(same139), dat_sha256=sha(target / 'GXRCE.DAT'),
                dat_bytes=(target / 'GXRCE.DAT').stat().st_size)


def main():
    manifest = json.loads((BUILT / 'manifest.json').read_text())
    assert manifest['generation'] == 148 and manifest['loader_request'] <= LIMIT, manifest['loader_request']
    release = (BUILT / 'GXRCE.DAT').read_bytes()
    assert hashlib.sha256(release).hexdigest() == manifest['sha256']
    import sys
    result = dict(loader_request=manifest['loader_request'], limit=LIMIT)
    if '--test-only' not in sys.argv:
        result['release'] = assemble(ROOT / 'firmware/package_v38_g139m', release)
    else:
        sealed = dict(reversed(l.split('  ', 1)) for l in (ROOT / 'firmware/package_v38_g139m/SHA256SUMS').read_text().splitlines())
        assert sealed['firmware/package_v38_g139m/local/SD_ROOT/GXRCE.DAT'] == manifest['sha256']
        result['release'] = dict(dat_sha256=manifest['sha256'], unchanged=True)
    staging = WORK / 'local/test-dat'
    staging.mkdir(parents=True, exist_ok=True)
    (staging / 'entries.txt').write_text(MANIFEST)
    built = staging / 'GXRCE.DAT'
    if built.exists():
        built.unlink()
    run = subprocess.run(['/usr/bin/python3', '-I', '-B', str(CLI), 'build', str(BUILT / 'GXRCE.DAT'),
                          '--manifest', str(staging / 'entries.txt'), '--output', str(built)],
                         capture_output=True, text=True, check=True)
    listing = json.loads(run.stdout)
    assert listing['count'] == 3 and len(built.read_bytes()) == len(release)
    grn = [e for e in listing['entries'] if e['base'] == 2]
    assert len(grn) == 1 and grn[0]['name'] == 'GRN*001' and \
        {k: v for k, v in grn[0]['levels'].items() if v} == {'Cont': 2, 'High': 5, 'Shad': 5, 'Satu': -5}, grn
    result['test'] = assemble(ROOT / 'firmware/package_v38_g139m_test', built.read_bytes())
    result['test']['entries'] = [e['name'] for e in listing['entries']]
    old = subprocess.run(['/usr/bin/python3', '-I', '-B', str(CLI), 'list', str(G139_TEST / 'GXRCE.DAT')],
                         capture_output=True, text=True, check=True)
    strip = lambda l: [{k: v for k, v in e.items() if k in ('name', 'base', 'levels')} for e in l['entries']]
    assert strip(json.loads(old.stdout)) == strip(listing), 'user entries differ from package_v38_g139_test'
    result['test']['entries_equal_g139_test'] = True
    (WORK / 'package.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
