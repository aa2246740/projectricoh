"""Run after make check exits successfully: verify receipts, inputs, scope, then clean task Scratch."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = ROOT / 'studio'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut-ident-r1')
os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            hasher.update(block)
    return hasher.hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=STUDIO, text=True).strip()


def main():
    suites = list(ET.parse(HERE / 'make-check.xml').getroot().iter('testsuite'))
    counts = {key: sum(int(s.get(key, '0')) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    assert counts['tests'] == 1579 and not any(counts[key] for key in ('failures', 'errors', 'skipped')), counts
    log = (HERE / 'make-check.log').read_text()
    summary = next(line for line in reversed(log.splitlines()) if re.match(r'^\d+ passed', line))
    assert summary.startswith('1579 passed') and 'rerun' not in summary and 'failed' not in summary
    warnings = re.search(r'(\d+) warnings?', summary)
    coverage = read('coverage.json')['totals']['percent_covered']
    assert coverage >= 85
    paths = [p for folder in ('src', 'tests', 'web', 'scripts') for p in (STUDIO / folder).rglob('*')
             if p.is_file() and p.suffix in ('.py', '.pyi', '.js', '.css', '.html', '.json', '.sql', '.md')]
    paths += [STUDIO / name for name in ('Makefile', 'pyproject.toml', 'uv.lock', 'docs/architecture.md')]
    after = {str(p.relative_to(STUDIO)): digest(p) for p in sorted(paths)}
    assert after == read('check-source-before.json'), 'Sources changed during make check'
    dump('check-source-after.json', after)
    for name, expected in read('after-sources.json').items():
        assert after[name] == expected, ('Real-file verification used another source', name)
    for name in ('src/gxr_studio/lut/spaces.py', 'src/gxr_studio/lut/scene.py'):
        assert after[name] == read('before-sources.json')[name], name

    inputs = {row['path']: row['sha256'] for row in read('after-imports.json') + read('after-photos.json')}
    for row in json.loads((ROOT / 'research/vlog_alchemy_eval/studio_photo_checks.json').read_text()):
        if 'jpeg' in row:
            inputs[row['jpeg']] = row['jpeg_sha256']
    inputs.update(read('reference-inputs.json'))
    for name, expected in inputs.items():
        assert digest(ROOT / name) == expected, ('Input changed', name)
    dump('input-stability.json', {'files': len(inputs), 'unchanged': True, 'sha256': inputs})

    expected_files = {
        'docs/architecture.md', 'src/gxr_studio/api/render_routes.py', 'src/gxr_studio/lut/cube.py',
        'src/gxr_studio/lut/identify.py', 'src/gxr_studio/lut/library.py', 'src/gxr_studio/lut/metadata.py',
        'src/gxr_studio/lut/photo.py', 'src/gxr_studio/lut/service.py', 'tests/test_lut_library.py',
        'tests/test_lut_ident_r1.py', 'web/assets/lut.js',
    }
    changed = set(git('diff', '--name-only').splitlines()) | set(git('ls-files', '--others', '--exclude-standard').splitlines())
    assert changed == expected_files, changed
    assert git('rev-parse', 'HEAD') == '6df3ff3606efcf8d6f6e075b1696b52de06ab1a8'
    assert not git('diff', '--cached', '--name-only'), 'Unexpected index changes'
    dump('changed-files.json', {name: after[name] for name in sorted(changed)})

    volume = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['DiskUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['FilesystemType'] == 'apfs'
    assert volume['WritableVolume'] and volume['MountPoint'] == '/Volumes/Workspace'
    commands = subprocess.check_output(['ps', '-axo', 'args='], text=True).splitlines()
    workers = [line for line in commands if line.startswith('/opt/homebrew/')
               and ' -m gxr_studio.lut.worker ' in line and str(SCRATCH) in line]
    assert workers == [], workers
    assert not SCRATCH.is_symlink() and SCRATCH.resolve() == SCRATCH
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    assert not SCRATCH.exists()
    dump('cleanup.json', {'scratch': str(SCRATCH), 'removed': True, 'remaining_lut_workers': workers,
                          'volume_uuid': volume['DiskUUID'], 'browser_profile_created': False})
    result = {'make_check_exit_code': 0, **counts, 'reruns': 0, 'warnings': int(warnings[1]) if warnings else 0,
              'coverage_percent': coverage, 'source_files_unchanged': len(after), 'inputs_unchanged': len(inputs),
              'studio_changed_files': len(changed), 'scratch_removed': True,
              'head': git('rev-parse', 'HEAD'), 'summary': summary}
    dump('receipt.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
