#!/usr/bin/python3
"""Verify frozen inputs, retain media, remove the owned temporary tree and seal."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(name, data):
    path = HERE / 'evidence' / name
    assert not path.exists(), path
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    now = datetime.datetime.now(datetime.timezone.utc)
    assert now < datetime.datetime.fromisoformat('2026-11-03T05:59:01+00:00')
    assert not (HERE / 'SHA256SUMS').exists()
    disk = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk.get('FilesystemType', '').lower() == 'apfs' and not disk.get('ReadOnlyVolume', False)
    assert disk['MountPoint'] == '/Volumes/Workspace'
    active = []
    for line in subprocess.check_output(['ps', '-ww', '-axo', 'pid=,ni=,args='], text=True).splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) != 3 or int(fields[0]) == os.getpid():
            continue
        executable = Path(fields[2].split(None, 1)[0]).name.lower()
        if 'python' in executable and 'research/review_v310_body_r1/' in fields[2]:
            active.append(line.strip())
    assert not active, active
    final = json.loads((HERE / 'evidence/final-behaviour-checks.json').read_text())
    assert final['status'] == 'PASS'
    nodat = []
    for unit, name in (('mount', 'nodat-mount-empty-r2-batch'), ('28mm', 'nodat-28mm-empty-batch'),
                       ('50mm', 'nodat-50mm-empty-batch')):
        run = json.loads((HERE / 'evidence' / (name + '.json')).read_text())
        assert run['status'] == 'PASS' and run['extra']['cycle_status'] == 'PASS'
        assert not any(v['operation'] == 257 for v in run['engine_calls'])
        assert run['rpc_write_count'] == 0 and run['extra']['later_colour_W'] == 0
        latches = [v for v in run['fixed_word_writes'] if v['size'] == 4 and v['value'] == 1]
        assert len(latches) == 1 and run['extra']['later_fixed_word_writes'] == 0
        nodat.append(dict(unit=unit, cold_steps=run['steps'], final_steps=run['extra']['final_steps'],
            first_latches=1, BOOT_calls=0, colour_W=0, later_fixed_word_writes=0))
    write('three-unit-nodat.json', dict(status='PASS', cases=nodat))
    provenance = []
    for name in ('nodat-mount-empty-r2-batch', 'nodat-28mm-empty-batch', 'nodat-50mm-empty-batch',
                 'valid-look-mount-batch', 'non-pure03-mount-batch'):
        run = json.loads((HERE / 'evidence' / (name + '.json')).read_text())
        extra = run['extra']
        assert extra['backend'] == 'original-batch' and extra['native_machine_used'] is False
        assert extra['actual_backend_module'] == str(ROOT / 'tools/gxr_emulator_standby/backend.py')
        assert run['library_sha256'] == '018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95'
        assert run['native_stats'] is None
        provenance.append(dict(case=name, shared_unused_backend_argument=run['backend'],
            actual_backend=extra['backend'], module=extra['actual_backend_module'],
            library_sha256=run['library_sha256'], native_machine_used=False))
    write('backend-provenance.json', dict(status='PASS', cases=provenance,
        note='The original batch module and library executed. The shared CLI argument native did not select the fast backend.'))
    deviation_path = HERE / 'evidence/process-limit-deviation.json'
    deviation = json.loads(deviation_path.read_text())
    comparisons = []
    for item in deviation['excluded']:
        original = HERE / item['original']
        retained = HERE / item['retained']
        assert digest(retained) == item['sha256']
        assert digest(original) == item['sha256']
        comparisons.append(dict(output=item['original'], rerun_bytes_equal=True))
    normalized = json.loads((HERE / 'evidence/non-pure04-mount-r2-batch.json').read_text())
    assert normalized['steps'] == 300000000
    row = next(v for v in normalized['engine_calls'] if v['operation'] == 257)
    assert row['before_context']['S_selector'] == 1
    allocation = [json.loads(line) for line in (HERE / 'evidence/process-allocation.jsonl').read_text().splitlines()]
    assert any(not v['allowed'] and len(v['active_before']) == 2 for v in allocation)
    deviation.update(status='CLOSED_WITH_DISCLOSED_DEVIATION', repeat_comparisons=comparisons,
        original_input_fresh_repeat='non-pure04-mount-r2-batch: selector 2 normalized to 1; not a non-04 test',
        intended_negative_replacement='non-pure03-mount-batch: actual selector 3, complete zero-write return',
        process_gate_REFUSE_observed=True,
        initial_gate_parser_correction='macOS truncates ps comm; final gate uses the executable token in wide args',
        final_gate_sha256=digest(HERE / 'review_launch.py'))
    deviation_path.write_text(json.dumps(deviation, ensure_ascii=False, indent=2) + '\n')
    frozen = json.loads((HERE / 'evidence/inputs-before.json').read_text())
    changed = []
    for index, (name, item) in enumerate(frozen['files'].items(), 1):
        path = ROOT / name
        if not path.is_file() or digest(path) != item['sha256']:
            changed.append(name)
        if index % 500 == 0:
            print(json.dumps(dict(stage='frozen-inputs', checked=index)), flush=True)
    write('inputs-after.json', dict(count=len(frozen['files']), changed=changed, unchanged=not changed))
    assert not changed, changed
    media_dir = HERE / 'local/media'
    media_dir.mkdir(exist_ok=True)
    media = []
    for path in sorted(TEMP.glob('*.img')):
        assert path.resolve().parent == TEMP and not path.is_symlink()
        sha = digest(path)
        target = media_dir / (sha + '.img')
        if not target.exists():
            shutil.copyfile(path, target)
        assert digest(target) == sha
        media.append(dict(original_name=path.name, sha256=sha, bytes=path.stat().st_size,
            retained=str(target.relative_to(ROOT))))
    write('review-media-retention.json', dict(status='PASS', media=media,
        unique_images=len({v['sha256'] for v in media}),
        scope='Exact review temporary images, including excluded attempts; model combinations are not changed by retention'))
    assert TEMP.resolve() == TEMP and not TEMP.is_symlink()
    files = [p for p in TEMP.rglob('*') if p.is_file()]
    count = len(files)
    total = sum(p.stat().st_size for p in files)
    shutil.rmtree(TEMP)
    assert not TEMP.exists()
    ended = datetime.datetime.now(datetime.timezone.utc)
    write('cleanup.json', dict(status='PASS', utc=ended.isoformat(),
        volume_UUID=disk['VolumeUUID'], original_frozen_inputs=len(frozen['files']), changed_inputs=[],
        temporary_path=str(TEMP), removed_files=count, removed_bytes=total,
        temporary_removed=True, residual_review_processes=active,
        review_scope='Implementation, packages and tools remained read-only; no camera/card, Git writes or subagents',
        process_limit_deviation_disclosed=True))
    report_path = HERE / 'REVIEW.md'
    report = report_path.read_text()
    old = '最终输入稳定性、清理和全部交付物 SHA 将在复审结束时登记。当前非纯 04 返回路径补查尚未收齐，本文件仍为复审中的版本。'
    assert report.count(old) == 1
    report = report.replace(old, '最终核对 2,992 个冻结输入，变化为 0；Scratch 临时目录已删除，复审运行残留为 0。见 [inputs-after.json](evidence/inputs-after.json)、[cleanup.json](evidence/cleanup.json) 和 [介质保留清单](evidence/review-media-retention.json)。SHA256SUMS 覆盖冻结输入及本复审全部交付文件，自身除外。封存时间为 ' + ended.isoformat() + '，在本轮 2.5 小时时间盒内。')
    report = report.replace('清理状态待最终收据。', '临时目录已清理，残留运行 0。')
    assert '补查中' not in report and '待最终' not in report and '复审中的版本' not in report
    assert report.splitlines()[0] == '可以刷'
    report_path.write_text(report)
    hashes = {name: item['sha256'] for name, item in frozen['files'].items()}
    for path in HERE.rglob('*'):
        if path.is_file() and path.name != 'SHA256SUMS' and path.name != '.DS_Store':
            hashes[str(path.relative_to(ROOT))] = digest(path)
    manifest = HERE / 'SHA256SUMS'
    manifest.write_text(''.join(sha + '  ' + name + '\n' for name, sha in sorted(hashes.items())))
    mismatches = [name for name, wanted in hashes.items() if digest(ROOT / name) != wanted]
    assert not mismatches, mismatches
    print(json.dumps(dict(status='SEALED', manifest_entries=len(hashes), inputs_unchanged=len(frozen['files']),
        temporary_removed=True, residual_review_processes=0, P1_body=0, P1_DAT=1)), flush=True)


if __name__ == '__main__':
    main()
