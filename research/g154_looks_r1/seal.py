"""核对受保护输入、最终包和所选作业，清理本轮 Scratch 并生成哈希。"""
from pathlib import Path
import argparse
import shutil
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from check_all import jobs, accepted_name


def sums(directory, extra=()):
    paths = set(extra)
    paths.update(p for p in directory.rglob('*') if p.is_file() and not p.is_symlink()
                 and p.name not in ('SHA256SUMS', '.gitignore', '.DS_Store') and '__pycache__' not in p.parts)
    output = directory / 'SHA256SUMS'
    output.write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in sorted(paths)))
    for line in output.read_text().splitlines():
        digest, relative = line.split('  ', 1)
        assert sha((ROOT / relative).read_bytes()) == digest, relative
    return len(paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', default='final')
    parser.add_argument('--cleanup', action='store_true', required=True)
    args = parser.parse_args()
    guard()
    digest = sha((PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes())
    accepted = []
    for name, _ in jobs():
        path = HERE / 'evidence' / ('job-' + accepted_name(args.prefix, name) + '.json')
        record = json.loads(path.read_text())
        assert record['status'] == 'PASS' and record['dat_sha256'][PACKAGE.name] == digest, path
        assert record['entry_sha256'] == sha((ROOT / record['argv'][0]).read_bytes()), path
        accepted.append(path.name)
    upgrades = [p for p in (BASE_PACKAGE / 'local/SD_ROOT').iterdir() if p.name != 'GXRCE.DAT']
    assert len(upgrades) == 29
    assert all(p.read_bytes() == (PACKAGE / 'local/SD_ROOT' / p.name).read_bytes() for p in upgrades)
    original = json.loads((HERE / 'frozen-inputs.json').read_text())
    changes = []
    for relative, expected in original.items():
        path = ROOT / relative
        actual = sha(path.read_bytes()) if path.is_file() else None
        if expected != actual:
            changes.append(dict(path=relative, before=expected, after=actual))
    required = [row for row in changes if not row['path'].startswith(('tools/gxr_emulator', 'studio/src/'))]
    emulator_changes = [row for row in changes if row['path'].startswith('tools/gxr_emulator')]
    studio_changes = [row for row in changes if row['path'].startswith('studio/src/')]
    codec_path = 'studio/src/gxr_studio/camdata/datcodec.py'
    codec_actual = sha((ROOT / codec_path).read_bytes())
    tested_codec = json.loads((HERE / 'evidence/data-checks.json').read_text())['studio']['datcodec_sha256']
    codec_stable = original[codec_path] == codec_actual == tested_codec
    source_equal = []
    for path in sorted(ENGINE.rglob('*')):
        if not path.is_file() or 'local' in path.relative_to(ENGINE).parts:
            continue
        relative = path.relative_to(ENGINE)
        old = BASE_ENGINE / relative
        if path.suffix in ('.c', '.h', '.S', '.ld'):
            assert old.is_file() and old.read_bytes() == path.read_bytes(), relative
            source_equal.append(str(relative))
    valid = not required and not emulator_changes and codec_stable
    status = 'PASS_WITH_CONCURRENT_STUDIO_CHANGES' if valid and studio_changes else 'PASS' if valid else 'FAIL'
    save(HERE / 'evidence/audit.json', dict(status=status,
        protected_files=len(original), protected_required_unchanged=not required,
        emulator_unchanged=not emulator_changes, studio_datcodec_unchanged=codec_stable,
        tested_datcodec_sha256=tested_codec, changes=changes,
        concurrent_studio_changes=studio_changes,
        studio_scope='Observed workspace drift outside this task; authorship not attributed. The standalone datcodec imports only standard-library modules; none of these changed files is imported by this verification.',
        unchanged_engine_C_headers_linker_sources=source_equal, upgrade_files_equal=29,
        final_dat_sha256=digest, accepted_jobs=accepted,
        boundary='No card access, no Git mutations, no emulator writes, no studio writes, no subagents.'))
    assert valid, changes
    misbound = json.loads((HERE / 'evidence/misbound-cleanup.json').read_text())
    assert misbound['status'] == 'PASS' and all(row['removed'] and not Path(row['path']).exists() for row in misbound['directories'])
    assert TMP == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-looks-r1') and not TMP.is_symlink()
    files_before = sum(p.is_file() for p in TMP.rglob('*'))
    shutil.rmtree(TMP)
    assert not TMP.exists()
    save(HERE / 'evidence/cleanup.json', dict(status='PASS', scratch=str(TMP),
        files_removed=files_before, scratch_removed=True, after_exists=TMP.exists(),
        preserved_binary_outputs=str((PACKAGE / 'local/evidence').relative_to(ROOT)),
        initial_rejected_candidate=str((PACKAGE / 'local/initial-candidate').relative_to(ROOT))))
    load(HERE / 'report.py', 'g154_looks_final_report').main(args.prefix)
    package_count = sums(PACKAGE)
    data_count = sums(DATA)
    extra = [p for p in ENGINE.rglob('*') if p.is_file() and not p.is_symlink()
             and p.name not in ('.gitignore', '.DS_Store') and '__pycache__' not in p.parts]
    extra += [p for p in PACKAGE.rglob('*') if p.is_file() and not p.is_symlink()
              and p.name not in ('.gitignore', '.DS_Store')]
    extra += [p for p in DATA.rglob('*') if p.is_file() and not p.is_symlink()]
    total = sums(HERE, extra)
    print(json.dumps(dict(status='PASS', final_dat_sha256=digest, protected_files=len(original),
         package_hash_entries=package_count, data_hash_entries=data_count, combined_hash_entries=total,
         scratch_removed=not TMP.exists())))


if __name__ == '__main__':
    main()
