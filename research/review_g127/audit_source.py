#!/usr/bin/python3
"""Check candidate source identity, changed functions and packaged code."""
from pathlib import Path
import hashlib
import difflib
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g127'
NEW = ROOT / 'firmware/engine_v48_own/candidate'
OLD = ROOT / 'firmware/engine_v47_fix/candidate'
FILES = {
    'containers/product/adapter.c': ['eng_settings_owned'],
    'containers/product/src/firmware/card_container_v2/gate.c': ['gxr2_tweak_layout'],
    'containers/product/src/firmware/engine/core/eng_core.c': ['apply_impl', 'eng_check_settings'],
    'containers/product/src/firmware/engine/core/eng_data.c': ['eng_data_accept'],
    'containers/product/ui_v2_data.c': ['uv_validate'],
    'engine_services/services.c': ['rv_settings_owned', 'settings', 'rv_service'],
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def function(text, name):
    found = re.search(r'(?m)^[^\n;{}]*\b'+re.escape(name)+r'\([^;{}]*\)\s*\{', text)
    if not found:
        return None
    begin = text.index('{', found.start())
    depth = 1
    cursor = begin + 1
    while depth:
        depth += (text[cursor] == '{') - (text[cursor] == '}')
        cursor += 1
    return text[found.start():cursor]

def main():
    assert __debug__ and sys.flags.optimize == 0
    sys.path.insert(0, str(ROOT / 'tools/native_harness'))
    from image_loader import Elf
    dat = (ROOT / 'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT').read_bytes()
    elf_path = NEW / 'local/full-r13/engine.elf'
    elf = Elf(elf_path)
    offset, length = [int.from_bytes(dat[n:n+4], 'big') for n in (132, 136)]
    section = next(s for s in elf.sections if s['name'] == '.engine')
    assert section['data'] == dat[offset:offset+length]
    assert sha(dat) == '9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'
    assert len(dat) == 58772 and int.from_bytes(dat[28:32], 'big') == 127
    changed_files=[]
    baseline={}
    for folder in ('containers/product','engine_services'):
        before_files={str(p.relative_to(OLD)) for p in (OLD/folder).rglob('*')
                      if p.is_file() and p.suffix in ('.c','.h','.S','.ld')}
        after_files={str(p.relative_to(NEW)) for p in (NEW/folder).rglob('*')
                     if p.is_file() and p.suffix in ('.c','.h','.S','.ld')}
        assert before_files==after_files
        for name in sorted(before_files):
            before,after=(OLD/name).read_bytes(),(NEW/name).read_bytes()
            baseline[str((OLD/name).relative_to(ROOT))]=sha(before)
            if before!=after:
                changed_files.append(name)
    expected=set(FILES)|{'containers/product/src/firmware/engine/core/eng_core.h',
                         'engine_services/engine_services.h'}
    assert set(changed_files)==expected
    provided=(ROOT/'research/g127_fix/source-change-vs-g126.patch').read_text()
    headers=[line[4:] for line in provided.splitlines() if line.startswith('--- ') or line.startswith('+++ ')]
    assembled=[]
    for index in range(0,len(headers),2):
        before,after=headers[index:index+2]
        assembled.extend(difflib.unified_diff((ROOT/before).read_text().splitlines(True),
            (ROOT/after).read_text().splitlines(True),fromfile=before,tofile=after,n=2))
    assert ''.join(assembled)==provided
    changed = []
    for path, names in FILES.items():
        current, previous = (NEW/path).read_text(), (OLD/path).read_text()
        for name in names:
            after, before = function(current, name), function(previous, name)
            assert after and before != after
            changed.append(dict(file=str((NEW/path).relative_to(ROOT)), function=name,
                                line=current[:current.index(after)].count('\n')+1,
                                added=before is None, source_sha256=sha(after.encode())))
    frozen = {}
    core = 'containers/product/src/firmware/engine/core/eng_core.c'
    for name in ('deep', 'rpc', 't_read', 't_store', 'write_word', 'recover_confirmed',
                 'make_plan', 'settings_match', 'rebind_impl', 'eng_require_recheck', 'validate_live'):
        before, after = function((OLD/core).read_text(), name), function((NEW/core).read_text(), name)
        assert before and after
        frozen[name] = before == after
    for name in ('record_failure', 'list_bind_impl', 'ig_event', 'ig_init'):
        path = 'containers/product/adapter.c'
        before, after = function((OLD/path).read_text(), name), function((NEW/path).read_text(), name)
        assert before and after
        frozen[name] = before == after
    for path,name in (('engine_services/native_seed.c','rv_view_owned'),
                      ('engine_services/services.c','ui_list')):
        before,after=function((OLD/path).read_text(),name),function((NEW/path).read_text(),name)
        assert before and after
        frozen[name]=before==after
    assert all(frozen.values())
    modes = []
    grain=[]
    for index, unit in enumerate(('50mm', '28mm', 'mount')):
        directory = int.from_bytes(dat[156:160], 'big') + 64*index
        bank = int.from_bytes(dat[directory+16:directory+20], 'big')
        record = dat[bank+32+64*3:bank+96+64*3]
        modes.append(dict(unit=unit, standard_slot=4, native_mode=record[3]))
        assert record[3] == 1
        table=int.from_bytes(dat[directory+20:directory+24],'big')
        flags=[dat[table+17+20*i] for i in range(dat[table+5])]
        grain.append(dict(unit=unit,flags=flags,grain_bit_clear=all(not flag&8 for flag in flags)))
    value = dict(status='PASS', dat_sha256=sha(dat), dat_bytes=len(dat), generation=127,
                 elf_sha256=sha(elf_path.read_bytes()), engine_bytes=length,
                 dat_engine_elf_equal=True, assertions_enabled=True,
                 changed_functions=changed, unchanged_functions=frozen, standard_modes=modes,
                 grain_descriptors=grain,changed_source_files=changed_files,
                 provided_patch_matches=True,baseline_hashes=baseline)
    (OUT/'source-audit.json').write_text(json.dumps(value, indent=2)+'\n')
    print('PASS', len(changed), 'changed functions;', len(frozen), 'unchanged functions; packaged code equal')

if __name__ == '__main__':
    main()
