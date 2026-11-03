"""Hash inputs and decode exact, section-mapped official UI routines."""
from pathlib import Path
import argparse
import datetime
import json
import plistlib
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT, OUT, file_sha, save, native_modules, sha

RANGES = [
    ('details_dispatch', 0x201fe900, 0x600),
    ('list_renderer', 0x201ffd68, 0x400),
    ('row_renderer', 0x201fdd10, 0x2060),
    ('draw_dispatch', 0x201fd360, 0x500),
    ('ascii_convert', 0x201d73e0, 0xc8),
    ('ascii_convert_body', 0x201d330c, 0x4b0),
    ('text_metrics', 0x201d74a8, 0x288),
    ('text_metrics_body', 0x201d2624, 0x320),
    ('glyph_width', 0x201d2fc0, 0x104),
    ('glyph_width_lookup', 0x201d3044, 0x7c),
    ('font_decoder', 0x201d2054, 0x1b0),
    ('resource_text_init', 0x201d1efc, 0x158),
    ('language_getter', 0x201dc168, 0x48),
    ('glyph_submit', 0x201d7170, 0x270),
    ('image_open', 0x20287080, 0x250),
    ('image_disp', 0x202be220, 0x180),
    ('image_move', 0x202bb900, 0x160),
    ('stock_details', 0x2023fd38, 0x90),
]


def snapshot():
    volume = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType'] == 'apfs' and volume['WritableVolume']
    paths = set()
    for root in ('firmware/engine_v44_keep/candidate',
                 'firmware/engine_v44_keep/native_harness',
                 'firmware/resident_v36/resident'):
        paths.update(p for p in (ROOT / root).rglob('*') if p.is_file()
                     and 'local' not in p.relative_to(ROOT / root).parts
                     and p.suffix in ('.py', '.c', '.h', '.S', '.ld'))
    for name in ('artifacts/firmware/gxr-1.51/ilaunch3',
                 'firmware/package_v36_g122/SD_ROOT/ilaunch3',
                 'firmware/package_v36_g122/SD_ROOT/GXRCE.DAT',
                 'firmware/resident_v36/local/resident/build/resident.elf',
                 'firmware/resident_v34c/local/resident/build/resident.elf',
                 'artifacts/firmware/gxr-1.51/ilaunch4',
                 'research/g122_keep_list/REPORT.md',
                 'research/g122_keep_list/resident-and-details-boundaries.json',
                 'research/emulator_feasibility_r1/prototype/boot_probe.py',
                 'research/ux_preview_dot_r5/native_names.py',
                 'research/ux_preview_dot_r5/REPORT.md',
                 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'):
        path = ROOT / name
        if path.is_file():
            paths.add(path)
    save('inputs-before.json', dict(
        started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        timebox_start_utc='2026-10-28T07:14:46Z', deadline_utc='2026-10-28T09:14:46Z',
        volume=dict(uuid=volume['VolumeUUID'], fs=volume['FilesystemType'], writable=True),
        files=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size,
                    sha256=file_sha(p)) for p in sorted(paths)]))


def decode():
    image_loader, backend, _ = native_modules()
    image = image_loader.Image(image_loader.OFFICIAL, image_loader.PINS['official'])
    image.verify_csv()
    rows = []
    directory = OUT / 'local/native'
    directory.mkdir(parents=True, exist_ok=True)
    for name, address, length in RANGES:
        data = image.bytes_at(address, length)
        binary = directory / (name + '.bin')
        binary.write_bytes(data)
        command = [str(backend.OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                   '--adjust-vma=' + hex(address), str(binary)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        binary.with_suffix('.txt').write_text(result.stdout)
        rows.append(dict(name=name, address=hex(address), bytes=length,
                         file_offset=hex(image.offset(address, length)), sha256=sha(data),
                         disassembly=str(binary.with_suffix('.txt').relative_to(ROOT))))
    save('native-ranges.json', dict(status='STATIC_DECODED', official_sha256=image.sha256,
                                  ranges=rows, scope='Static instructions; no camera execution.'))


def verify():
    before = json.loads((OUT / 'inputs-before.json').read_text())
    extra = OUT / 'inputs-extra.json'
    rows = before['files'] + (json.loads(extra.read_text())['files'] if extra.exists() else [])
    changes = []
    for row in rows:
        path = ROOT / row['path']
        after = file_sha(path) if path.is_file() else None
        if after != row['sha256']:
            changes.append(dict(path=row['path'], before=row['sha256'], after=after))
    save('input-integrity.json', dict(status='PASS' if not changes else 'INPUT_CHANGED',
         files_checked=len(rows), changes=changes,
         scope='Selected inputs only; concurrent research directories remain read-only.'))
    print('input check:', len(rows), 'files;', len(changes), 'changes')


def extend():
    before = json.loads((OUT / 'inputs-before.json').read_text())
    held = {row['path']: row['sha256'] for row in before['files']}
    names = [str(p.relative_to(ROOT)) for p in (ROOT / 'tools/native_harness').glob('*.py')]
    names.extend(('artifacts/firmware/gxr-1.51/ilaunch4',
        'artifacts/firmware/gxr-1.51/jlaunch3', 'artifacts/firmware/gxr-1.51/qlaunch3',
        'firmware/package_v36_g117/SD_ROOT/l08firm3',
        'firmware/image_v36/local/package/SD_ROOT/ilaunch3',
        'firmware/engine_v44_keep/native_binding.py',
        'firmware/engine_v44_keep/integration_native.py',
        'firmware/engine_v44_keep/candidate/local/full-r13/engine.elf',
        'research/firmware/ilaunch3-sections.csv',
        'research/stage1_ui/text-FINDINGS.md',
        'research/stage1_ui/lever-check.py',
        'research/three_module_audit_r1/audit.py'))
    path = OUT / 'inputs-extra.json'
    rows = json.loads(path.read_text())['files'] if path.exists() else []
    held.update({row['path']: row['sha256'] for row in rows})
    for name in sorted(set(names)):
        actual = file_sha(ROOT / name)
        if name in held:
            assert actual == held[name], name
        else:
            rows.append(dict(path=name, bytes=(ROOT / name).stat().st_size, sha256=actual))
    save('inputs-extra.json', dict(note='Additional read dependencies; existing pins are never refreshed.',
        files=sorted(rows, key=lambda x: x['path'])))
    print('additional inputs:', len(rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'decode', 'verify', 'extend'))
    args = parser.parse_args()
    {'snapshot': snapshot, 'decode': decode, 'verify': verify, 'extend': extend}[args.action]()
