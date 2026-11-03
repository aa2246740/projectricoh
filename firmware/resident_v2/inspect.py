#!/usr/bin/env python3
"""Targeted owner-firmware evidence. Writes only this task's ignored local/."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
IMAGE = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
IMAGE_SHA = 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
EXTRA = [
    ('boot', 0x20055074), ('heap_new', 0x2005bf00),
    ('segment_main', 0x20088358), ('segment_alt', 0x20088e5c),
    ('link_store', 0x200935dc), ('unit_receive', 0x200637e0),
    ('unit_power', 0x200630f4), ('sd_init', 0x200a3568),
    ('mode_dispatch', 0x20069d4c), ('playback_before_effects', 0x202fb9cc),
    ('shutdown', 0x2005cf7c), ('sleep_state', 0x20060300),
    ('sleep_d0', 0x200600d0), ('sleep_15c', 0x2006015c),
    ('raw_mode_a', 0x20069c98), ('raw_mode_b', 0x2006940c),
    ('volume_operation', 0x20111810), ('unit_update_cleanup', 0x2010d70c),
    ('playback_caller_1', 0x20373e48), ('playback_caller_2', 0x20373e88),
    ('playback_caller_3', 0x20373fd4), ('playback_caller_4', 0x20374030),
    ('preview_observer', 0x202d6f38),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info.get('MountPoint') == '/Volumes/Workspace'
    assert info.get('FilesystemType') == 'apfs'
    assert info.get('VolumeUUID') == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info.get('WritableVolume') and os.access('/Volumes/Workspace', os.W_OK)
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v2')
    check = subprocess.check_output(['git', 'check-ignore', '-v', 'firmware/resident_v2/local/check'], cwd=ROOT, text=True)
    assert 'firmware/resident_v2/.gitignore:1:/local/' in check
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    return info, check


def offset(image, va, length):
    matches = []
    for i in range(16):
        source, start, size, _, _ = struct.unpack_from('>5I', image, 0x20+20*i)
        if start <= va and va+length <= start+size:
            matches.append((i, source+512+va-start))
    assert len(matches) == 1, hex(va)
    return matches[0]


def collect():
    info, check = preflight()
    assert sha(IMAGE) == IMAGE_SHA
    image = IMAGE.read_bytes()
    hooks = json.loads((ROOT / 'research/tweak_panel_ui/local/hook_candidates.json').read_text())
    hooks += [dict(id=name, va=hex(va), length=4, status='v2_observer_or_guard') for name, va in EXTRA]
    rows = ['# v2 hook 官方原字节附件', '', '逐项来自只读官方 MAIN。没有新补丁字节或固件映像。', '',
            '| ID | 名称 | 地址 | 长度 | 官方原字节 | 默认续接 |',
            '|---|---|---|---:|---|---|']
    for i, hook in enumerate(hooks, 1):
        va, n = int(hook['va'], 16), hook['length']
        seg, off = offset(image, va, n)
        original = image[off:off+n].hex()
        assert original == hook.get('original_bytes', original), hook['id']
        hook.update(number=i, segment=seg, file_offset=hex(off), original_bytes=original,
                    replay_resume=hex(va+n))
        rows.append(f"| H{i:02} | {hook['id']} | {va:#010x} | {n} | `{original}` | {va+n:#010x} |")
        if hook['id'] not in ('adj_name_table', 'adj_count_16'):
            begin, end = max(va-8, va & ~3), va+48
            _, win_off = offset(image, begin, end-begin)
            raw = LOCAL / f'H{i:02}.bin'
            raw.write_bytes(image[win_off:win_off+end-begin])
            asm = subprocess.check_output([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                                           f'--adjust-vma={begin}', str(raw)], text=True)
            (LOCAL / f'H{i:02}.asm.txt').write_text(asm)
    (LOCAL / 'hooks.json').write_text(json.dumps(hooks, ensure_ascii=False, indent=2)+'\n')
    (LOCAL / 'HOOKS.md').write_text('\n'.join(rows)+'\n')
    _, free_off = offset(image, 0x2005276c, 8340)
    assert image[free_off:free_off+8340] == bytes([255])*8340
    (LOCAL / 'volume.json').write_text(json.dumps({k:info.get(k) for k in
        ('MountPoint','FilesystemType','VolumeUUID','WritableVolume')}, indent=2)+'\n')
    (LOCAL / 'ignore.txt').write_text(check)
    inputs = [IMAGE, OBJDUMP, ROOT/'firmware/card_container/gxrce.c', ROOT/'firmware/card_container/gxrce.h']
    inputs += [ROOT/p for p in ('research/card_engine/REPORT.md','research/irom_storage/REPORT.md',
        'research/irom_storage/STORAGE_ABI.md','research/tweak_panel_ui/REPORT.md',
        'research/tweak_panel_ui/local/HOOKS.md','research/tweak_panel_ui/local/hook_candidates.json',
        'research/engine_lifecycle/REPORT.md','research/engine_lifecycle/PROBES.md',
        'firmware/card_container/FORMAT.md','research/recipe_tweak/REPORT.md',
        'research/recipe_tweak/tweak_int.c','research/recipe_tweak/tweak_int.h',
        'firmware/stage2l_switch/hooks.json','firmware/stage2l_switch/abi.S',
        'firmware/stage2l_switch/tools/build.py','firmware/stage2l_switch/payload.ld',
        'firmware/stage2l_switch/build/payload.map','firmware/stage2l_switch/README.txt',
        'firmware/stage2l_switch/recipe_v1/recipe_apply.c','firmware/stage2l_switch/recipe_v1/recipe_v1.h',
        'firmware/stage2l_switch/foreign.h','firmware/stage2l_switch/deep_isp.h',
        'firmware/stage2k_p0/probe.S','firmware/stage2k_p0/module.c',
        'research/stage1_data/REPORT.md',
        'firmware/card_container/pack.py','firmware/card_container/local/candidate/GXRCE.DAT',
        'firmware/card_container/local/candidate/trust.bin',
        'artifacts/firmware/gxr-1.51/jlaunch3','artifacts/firmware/gxr-1.51/qlaunch3',
        'artifacts/firmware/gxr-1.51/l08firm3',
        'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/manifest.json',
        'research/stage2k_design/REPORT.md','research/stage2k_design/FOLLOWUP.md')]
    inputs += list((ROOT/'firmware/stage2l_switch').glob('*.c'))
    (LOCAL / 'inputs.json').write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in inputs}, indent=2)+'\n')
    print(f'PASS_STATIC hooks={len(hooks)} official_window=8340B_all_ff ignore=task_local')


if __name__ == '__main__':
    collect()
