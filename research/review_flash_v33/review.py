#!/usr/bin/python3
"""Read-only frozen-candidate review. All outputs remain beside this script."""
import argparse
import hashlib
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
PYTHON = ['/usr/bin/python3', '-I', '-B']
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'

def digest(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def write(name, value):
    p = LOCAL / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def run(cmd, log=None, **kwargs):
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'),
        CLANG_MODULE_CACHE_PATH=str(LOCAL/'tmp/modules'),
        ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
        PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
    p = subprocess.run([str(x) for x in cmd], cwd=ROOT, text=True,
                       env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    if log:
        f = LOCAL / log
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(p.stdout)
        with (LOCAL / 'commands.jsonl').open('a') as f:
            f.write(json.dumps(dict(argv=[str(x) for x in cmd], rc=p.returncode, log=log))+'\n')
    if p.returncode:
        raise RuntimeError(f'command exit {p.returncode}: {cmd}: {p.stdout[-4000:]}')
    return p.stdout

def preflight():
    p = subprocess.run(['diskutil', 'info', '-plist', '/Volumes/Workspace'],
                       check=True, stdout=subprocess.PIPE)
    v = plistlib.loads(p.stdout)
    assert v['MountPoint'] == '/Volumes/Workspace'
    assert v['VolumeUUID'] == UUID
    assert v['FilesystemType'].lower() == 'apfs'
    assert v['WritableVolume'] and v['WritableMedia']
    assert os.access('/Volumes/Workspace', os.W_OK)
    df = subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True,
                        text=True, stdout=subprocess.PIPE).stdout
    LOCAL.mkdir(parents=True, exist_ok=True)
    write('preflight.json', {'volume': v, 'df': df, 'cwd': str(ROOT)})
    (LOCAL / 'df.txt').write_text(df)
    return df

def protected():
    dirs = ['firmware/resident_v33', 'firmware/image_v33', 'firmware/resident_v32',
            'firmware/engine_v33d', 'firmware/engine_v33c', 'firmware/engine_v33b',
            'firmware/engine_fix_r2', 'firmware/stage2l_mount',
            'firmware/stage2l_restore', 'firmware/stage2l_switch',
            'firmware/image_v3', 'artifacts/firmware/gxr-1.51',
            'research/review_flash_v32', 'research/review_full_r4',
            'research/review_full_r6', 'research/review_full_r7',
            'research/review_engine_fix_r2', 'research/bw03_standard_mode']
    files = {}
    for name in dirs:
        for p in sorted((ROOT / name).rglob('*')):
            if p.is_file() and not p.is_symlink() and p.name != 'decisions.tsv':
                files[str(p.relative_to(ROOT))] = {'bytes': p.stat().st_size,
                                                  'sha256': digest(p)}
    return files

def freeze():
    assert not (LOCAL / 'inputs-before.json').exists(), 'freeze exists; do not overwrite'
    preflight()
    write('inputs-before.json', protected())
    (LOCAL / 'git-status-before.txt').write_text(run(['git', 'status', '--porcelain=v1', '-uno']))
    print('frozen inputs:', len(json.loads((LOCAL / 'inputs-before.json').read_text())))

def unchanged():
    before = json.loads((LOCAL / 'inputs-before.json').read_text())
    after = protected()
    changes = {k: {'before': before.get(k), 'after': after.get(k)}
               for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)}
    status = run(['git', 'status', '--porcelain=v1', '-uno'])
    old_status = (LOCAL / 'git-status-before.txt').read_text()
    keep = lambda s: '\n'.join(x for x in s.splitlines() if not x.endswith(' decisions.tsv'))
    write('inputs-final.json', {'files': len(before), 'changes': changes,
          'tracked_status_unchanged': keep(status) == keep(old_status), 'git_status': status})
    assert not changes, f'{len(changes)} protected input changes'
    assert keep(status) == keep(old_status)
    print('protected inputs unchanged:', len(before))

def sums():
    lines = []
    for p in sorted(HERE.rglob('*')):
        if p.is_file() and p.name != 'SHA256SUMS':
            lines.append(f'{digest(p)}  {p.relative_to(HERE)}')
    (HERE / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print('SHA256SUMS entries:', len(lines))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['freeze', 'unchanged', 'sums'])
    args = parser.parse_args()
    globals()[args.action]()
