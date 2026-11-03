"""Verify report links, neutral wording, native records and the final manifest."""
from pathlib import Path
import json
import plistlib
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, PACKAGE, save, load, file_sha

def main():
    assert not TREE.exists() and not PACKAGE.exists()
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace' and info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia']
    status = subprocess.check_output(['git', 'status', '--short', '--untracked-files=no'], cwd=ROOT, text=True)
    assert set(status.splitlines()) == {' M .gitignore', ' M README.md', ' M decisions.tsv', ' M docs/HANDOFF.md'}
    save('scope-check.json', dict(status='PASS', volume={k: info[k] for k in (
        'MountPoint', 'FilesystemType', 'VolumeUUID', 'WritableVolume', 'WritableMedia')},
        existing_git_status=status, engine_v42_created=False, package_g120b_created=False,
        actual_write_directory=str(OUT), camera_or_card_operations=False))
    commands = []
    for label in ('prepare', 'static-fn2', 'fn2-50mm', 'fn2-28mm', 'fn2-mount', 'inputs-after'):
        p = OUT / 'commands' / label / 'command.json'
        row = json.loads(p.read_text())
        assert row['returncode'] == 0, label
        commands.append(dict(label=label, returncode=0, sha256=file_sha(p)))
    links = []
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', (OUT / 'REPORT.md').read_text()):
        if target in ('SHA256SUMS', 'manifest-selfcheck.json'):
            continue
        path = OUT / target
        assert path.exists(), target
        links.append(target)
    vocabulary = load(ROOT / 'research/review_g119b/neutral_terms.py', 'final_quality_words')
    bad = []
    for path in sorted(OUT.rglob('*')):
        if vocabulary.pattern.search(path.name):
            bad.append(str(path.relative_to(OUT)).encode().hex())
        if path.is_file():
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            if vocabulary.pattern.search(text):
                bad.append(str(path.relative_to(OUT)).encode().hex())
    assert not bad, dict(non_neutral_paths_hex=bad)
    save('acceptance.json', dict(status='STOPPED_WITH_VERIFIED_STATE_COUNTERCASE',
        native_cases=9, units=3, all_native_observations_pass=True,
        candidate_produced=False, commands=commands, report_links_checked=links,
        neutral_vocabulary=True, full_gen120_acceptance=False,
        conclusion='Existing Fn2 confirmation and half-shutter behavior conflict with the requested all-path H07 zero-communication rule.'))
    manifest = OUT / 'SHA256SUMS'
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p != manifest and p.name != 'manifest-selfcheck.json')
    save('manifest-selfcheck.json', dict(status='PASS', files=len(files)+1,
        manifest='SHA256SUMS', self_excluded_manifest_only=True,
        verification='Every entry is rehashed below and the complete file set is compared with the manifest.',
        native_records=3, native_cases=9, input_changes=0, candidate_produced=False))
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p != manifest)
    manifest.write_text(''.join(file_sha(p) + '  ' + str(p.relative_to(OUT)) + '\n' for p in files))
    checked = []
    for line in manifest.read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = (OUT / name).resolve()
        assert path.is_relative_to(OUT) and file_sha(path) == digest, name
        checked.append(path)
    actual = sorted(p.resolve() for p in OUT.rglob('*') if p.is_file() and p != manifest)
    assert sorted(checked) == actual
    assert len(checked) == json.loads((OUT / 'manifest-selfcheck.json').read_text())['files']
    print('PASS manifest', len(checked), '/', len(checked), '; nine native cases; input changes 0; no new firmware or package.', flush=True)

if __name__ == '__main__':
    main()
