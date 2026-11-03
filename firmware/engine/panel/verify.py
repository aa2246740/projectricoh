#!/usr/bin/env python3
"""Run host faults and measure M32R objects. No card image or firmware output."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'
SOURCES = ['panel_port.c', 'panel_store.c', 'panel_ui.c', 'panel.c', 'panel_gxts.c',
           'panel_gxts_bind.c', 'panel_native.c']
GXTS_SOURCES = [ROOT / 'firmware/card_container_v2' / s
               for s in ['common.c', 'gxts.c', 'gxts_io.c']]
CORE_HEADER = '-DPN_CORE_HEADER="../core/eng_core.h"'
CRC_PROFILE = '-Dgxr2_sha256=pn_gxts_crc_field'
EXPECTED_UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
ENGINE_BUDGET = 32768


def preflight():
    v = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert v['MountPoint'] == '/Volumes/Workspace'
    assert v['FilesystemType'] == 'apfs' and v['WritableVolume']
    assert v.get('VolumeUUID', v.get('DiskUUID')) == EXPECTED_UUID
    assert os.access('/Volumes/Workspace', os.W_OK)
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine/panel')
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    (LOCAL / 'volume.json').write_text(json.dumps(v, indent=2) + '\n')


def run(argv, name):
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C',
               PYTHONDONTWRITEBYTECODE='1', ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    p = subprocess.run([str(x) for x in argv], cwd=HERE, env=env,
                       text=True, capture_output=True)
    (LOCAL / (name + '.log')).write_text(p.stdout + p.stderr)
    commands.append({'name': name, 'argv': [str(x) for x in argv], 'returncode': p.returncode})
    (LOCAL / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    if p.returncode:
        failures = LOCAL / 'failures'
        failures.mkdir(exist_ok=True)
        index = len(list(failures.iterdir())) + 1
        (failures / f'{index:03}-{name}.log').write_text(p.stdout + p.stderr)
        raise RuntimeError(f'{name}: exit={p.returncode}\n{p.stderr[-1800:]}')
    return p.stdout


def host():
    out = LOCAL / 'host-final'
    flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
             '-fno-omit-frame-pointer', '-fsanitize=address,undefined']
    run(['clang', *flags, CORE_HEADER, CRC_PROFILE, *SOURCES, *GXTS_SOURCES,
         'tests/host_checks.c', '-o', out], 'host-build')
    run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsyntax-only',
         *SOURCES], 'fallback-core-contract-check')
    result = run([out, LOCAL / 'fault-matrix.tsv'], 'host-checks')
    print(result.strip())
    return {'sanitizers': ['ASan', 'UBSan'], 'stdout': result.strip(),
            'cases': sum(1 for _ in (LOCAL / 'fault-matrix.tsv').open())}


def elf(path):
    b = path.read_bytes()
    assert b[:6] == b'\x7fELF\x01\x02', 'expected ELF32 big endian M32R'
    off = struct.unpack_from('>I', b, 32)[0]
    ent, count, strings = struct.unpack_from('>HHH', b, 46)
    headers = [struct.unpack_from('>10I', b, off + ent * i) for i in range(count)]
    st = headers[strings]
    names = b[st[4]:st[4]+st[5]]
    def string(data, start):
        return data[start:data.index(b'\0', start)].decode()
    sections = []
    for h in headers:
        sections.append(dict(name=string(names, h[0]), type=h[1], flags=h[2],
                             size=h[5], offset=h[4], entry=h[9], link=h[6]))
    symbols = []
    for s in sections:
        if s['type'] != 2:
            continue
        st = sections[s['link']]
        table = b[st['offset']:st['offset']+st['size']]
        for p in range(s['offset'], s['offset']+s['size'], s['entry']):
            name, value, size, info, other, index = struct.unpack_from('>IIIBBH', b, p)
            if name:
                symbols.append(dict(name=string(table, name), size=size, section=index))
    return sections, symbols


def measure():
    # Import only constants from the user's existing builder. It has no import-time writes.
    import importlib.util
    spec = importlib.util.spec_from_file_location('read_only_resident_builder', ROOT / 'firmware/resident_v2/build.py')
    resident = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resident)
    gcc, ld = resident.GCC, resident.LD
    assert gcc.is_file() and ld.is_file(), 'existing M32R toolchain missing'
    out = LOCAL / 'final-m32r'
    out.mkdir(exist_ok=True)
    objects = []
    flags = [*resident.FLAGS, '-mmodel=medium', CORE_HEADER, CRC_PROFILE]
    for source in SOURCES:
        obj = out / (Path(source).stem + '.o')
        run([gcc, *flags, '-I', HERE, '-c', HERE / source, '-o', obj], 'm32r-' + Path(source).stem)
        objects.append(obj)
    combined = out / 'engine-panel.o'
    run([ld, '-r', '-o', combined, *objects], 'm32r-relocatable-link')
    sections, symbols = elf(combined)
    counts = {key: sum(s['size'] for s in sections if s['name'].startswith(prefix))
              for key, prefix in [('text', '.text'), ('rodata', '.rodata'), ('data', '.data'), ('bss', '.bss')]}
    undefined = sorted(s['name'] for s in symbols if s['section'] == 0)
    allowed = {'eng_apply', 'eng_current', 'eng_metadata', 'eng_uncertain', 'memcpy', 'memset',
               'gxts_bind', 'gxts_load', 'gxts_defaults', 'gxts_save', 'gxts_decode',
               'gxr2_crc32', 'gxr2_crc_begin', 'gxr2_crc_add', 'gxr2_crc_end', 'gxr2_raw_row'}
    assert set(undefined) <= allowed, undefined
    shared = []
    for source in GXTS_SOURCES:
        obj = out / ('shared-' + source.stem + '.o')
        run([gcc, *flags, '-I', HERE, '-c', source, '-o', obj], 'm32r-shared-' + source.stem)
        shared.append(obj)
    shared_bytes = {}
    for obj in shared:
        sec, _ = elf(obj)
        shared_bytes[obj.name] = sum(s['size'] for s in sec
                                    if s['name'].startswith(('.text', '.rodata')))
    # Stubs exist ONLY for resolving an executable measurement. They never run
    # on a camera and are excluded from the reported panel.o module sizes.
    (out / 'link_stubs.c').write_text('''#include "panel.h"
EngStatus eng_apply(const EngRecipeRef *r,const EngTweak *t){(void)r;(void)t;return ENG_REJECTED;}
EngStatus eng_current(EngRecipeRef *r,EngTweak *t){(void)r;(void)t;return ENG_REJECTED;}
EngStatus eng_metadata(uint8_t s,int8_t a[8],int8_t b[8],int8_t c[8]){(void)s;(void)a;(void)b;(void)c;return ENG_REJECTED;}
int eng_uncertain(void){return 1;}
void *memcpy(void *d,const void *s,unsigned n){unsigned char *a=d;const unsigned char *b=s;while(n--)*a++=*b++;return d;}
void *memset(void *d,int v,unsigned n){unsigned char *a=d;while(n--)*a++=(unsigned char)v;return d;}
''')
    stub = out / 'link_stubs.o'
    run([gcc, *flags, '-I', HERE, '-c', out / 'link_stubs.c', '-o', stub], 'm32r-link-stubs')
    (out / 'measurement.ld').write_text('''SECTIONS {
 . = 0x10000000;
 .text : { *(.text*) }
 .rodata : { *(.rodata*) }
 .data : { *(.data*) *(.sdata*) }
 .bss (NOLOAD) : { *(.bss*) *(.sbss*) *(COMMON) }
 .rela.got : { *(.rela.got) }
 /DISCARD/ : { *(.comment) *(.note*) }
}
''')
    linked = out / 'measurement-only.elf'
    run([ld, '--no-undefined', '--orphan-handling=error', '-T', out / 'measurement.ld',
         '-Map=' + str(out / 'measurement.map'), '-o', linked, combined, stub, *shared], 'm32r-measurement-link')
    _, linked_symbols = elf(linked)
    assert not [s for s in linked_symbols if s['section'] == 0]
    assert not [s['name'] for s in linked_symbols if 'sha' in s['name'].lower()], 'SHA symbol in camera-side ELF'
    run([resident.OBJDUMP, '-d', linked], 'm32r-disassembly')
    (out / 'layout.c').write_text('''#include "panel.h"
#include "panel_gxts.h"
const unsigned char size_PnPanel[sizeof(PnPanel)]={0};
const unsigned char size_PsStore[sizeof(PsStore)]={0};
const unsigned char size_PnGxts[sizeof(PnGxts)]={0};
''')
    run([gcc, *flags, '-I', HERE, '-c', out / 'layout.c', '-o', out / 'layout.o'], 'm32r-layout')
    _, sizes = elf(out / 'layout.o')
    usage = []
    for p in sorted(out.glob('*.su')):
        if p.stem in {Path(s).stem for s in SOURCES}:
            usage.extend(p.read_text().splitlines())
    result = dict(measurement_only=True, flags=flags, module_bytes=counts,
                  code_rodata=counts['text']+counts['rodata'], undefined=undefined,
                  shared_gxts_library_code_rodata=shared_bytes,
                  panel_with_gxts=counts['text']+counts['rodata']+sum(shared_bytes.values()),
                  engine_code_budget=ENGINE_BUDGET,
                  no_sha_symbols=True,
                  layout={s['name'][5:]: s['size'] for s in sizes if s['name'].startswith('size_')},
                  stack_usage=usage,
                  tools={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in [gcc, ld, resident.OBJDUMP]})
    (LOCAL / 'size.json').write_text(json.dumps(result, indent=2) + '\n')
    print('M32R panel code+rodata=' + str(result['code_rodata']) + ' B')
    return result


def pic_budget(profile='compact'):
    """Read-only core sources + panel, all outputs remain in this task's local/."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('resident_pic_constants', ROOT / 'firmware/resident_v2/build.py')
    resident = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resident)
    out = LOCAL / 'pic-budget' / profile
    out.mkdir(parents=True,exist_ok=True)
    flags = [*resident.FLAGS, '-mmodel=medium', '-fpic', '-fvisibility=hidden',
             '-ffunction-sections', '-fdata-sections', '-falign-functions=4']
    if profile in ['compact','lto_compact']:
        flags += ['-fno-inline-small-functions', '-fno-inline-functions-called-once']
    if profile.startswith('lto'):
        flags.append('-flto')
    roots = ['pn_panel_init', 'pn_panel_open', 'pn_panel_event', 'pn_panel_notify',
             'pn_panel_cancel', 'pn_native_from_seed', 'pn_gxts_bind', 'pn_gxts_load',
             'pn_gxts_save', 'ps_init', 'ps_install']
    script = out / 'measurement.ld'
    script.write_text('''__image_base = 0x10000000;
SECTIONS {
 . = 0x10000000;
 .engine : { *(.text*) *(.rodata*) *(.got*) *(.data*) *(.sdata*) }
 .bss (NOLOAD) : { *(.bss*) *(.sbss*) *(COMMON) }
 .rela.got 0 : { *(.rela.got) }
 /DISCARD/ : { *(.comment) *(.note*) }
}
''')
    panel = []
    for source in [HERE / s for s in SOURCES] + GXTS_SOURCES:
        obj = out / ('panel-' + source.stem + '.o')
        run([resident.GCC, *flags, CORE_HEADER, CRC_PROFILE, '-c', source, '-o', obj], 'pic-panel-' + source.stem)
        panel.append(obj)
    stubs = out / 'stubs.o'
    # Keep measurement stubs opaque to LTO. Otherwise constant stub returns
    # would erase the successful panel paths and undercount the real work.
    run([resident.GCC, *flags, '-fno-lto', '-I', HERE, '-c',
         LOCAL / 'final-m32r/link_stubs.c', '-o', stubs], 'pic-core-stubs')
    stub_sizes = {}
    def link(objects, name, entries):
        path = out / (name + '.elf')
        options = ['--no-undefined', '--gc-sections', '-Bsymbolic', '--orphan-handling=error',
                   *['--undefined=' + n for n in entries], '-T', script,
                   '-Map=' + str(out / (name + '.map'))]
        if profile.startswith('lto'):
            argv = [resident.GCC, *flags, '-nostdlib', *['-Wl,'+str(x) for x in options],
                    '-o', path, *objects]
        else:
            argv = [resident.LD, *options, '-o', path, *objects]
        run(argv, 'pic-' + profile + '-link-' + name)
        sections, symbols = elf(path)
        assert not [s for s in symbols if s['section'] == 0]
        assert not [s for s in symbols if 'sha' in s['name'].lower()]
        stub_sizes[name] = sum(s['size'] for s in symbols if s['name'] in
                             {'eng_apply','eng_current','eng_metadata','eng_uncertain','memcpy','memset'})
        return next(s['size'] for s in sections if s['name'] == '.engine')
    panel_bytes = link([*panel, stubs], 'panel', roots)
    core_sources = [ROOT / 'firmware/engine/core' / s for s in
        ['eng_data.c', 'eng_crc_compat.c', 'eng_semantic.c', 'eng_pin_stub.c', 'eng_core.c',
         'eng_grain.c', 'eng_entries.c', 'eng_mem.c']]
    core_sources += [ROOT / 'research/recipe_tweak/r2/tweak_int.c']
    core = []
    for source in core_sources:
        obj = out / ('core-' + source.stem + '.o')
        run([resident.GCC, *flags, *(['-fno-lto'] if source.stem=='eng_mem' else []),
             '-c', source, '-o', obj], 'pic-' + profile + '-core-' + source.stem)
        core.append(obj)
    shared_bind = out / 'panel-shared-parameter.o'
    run([resident.GCC, *flags, CORE_HEADER, CRC_PROFILE, '-DPN_GXTS_SHARED_PARAMETER', '-c',
         HERE / 'panel_gxts_bind.c', '-o', shared_bind], 'pic-shared-parameter')
    shared_crc = out / 'panel-shared-crc.o'
    run([resident.GCC, *flags, '-Dgxr2_sha256=eng_crc_binding', '-c',
         ROOT / 'firmware/card_container_v2/gxts.c', '-o', shared_crc], 'pic-shared-core-crc')
    combined_panel = [p for p in panel if p.name not in
                      ['panel-panel_gxts_bind.o','panel-gxts.o']] + [shared_bind,shared_crc]
    total = link([*combined_panel, *core], 'core-and-panel', ['eng_bootstrap', *roots])
    result = dict(panel_with_gxts_and_stub_bytes=panel_bytes, core_and_panel_bytes=total,
                  panel_measurement_stub_function_bytes=stub_sizes['panel'],
                  panel_without_stub_function_bodies=panel_bytes-stub_sizes['panel'],
                  target=ENGINE_BUDGET, within_target=total <= ENGINE_BUDGET,
                  excess=max(0,total-ENGINE_BUDGET),
                  remaining_for_core=ENGINE_BUDGET-panel_bytes, no_sha_symbols=True,
                  profile=profile,flags=flags, roots=roots, runtime_wiring_tested=False,
                  engine_services_included=False,
                  source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in core_sources})
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'PIC {profile}: panel+GXTS+stubs={panel_bytes} core+panel={total} budget={ENGINE_BUDGET} excess={result["excess"]}')
    return result


def sums():
    rows = []
    for p in sorted(HERE.rglob('*')):
        if p.is_file() and p.name != 'SHA256SUMS':
            rel = p.relative_to(HERE)
            if 'tmp' not in rel.parts and '.dSYM' not in str(rel):
                rows.append(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(rel))
    (HERE / 'SHA256SUMS').write_text('\n'.join(rows) + '\n')


def inputs():
    paths = [HERE / s for s in SOURCES] + list(HERE.glob('*.h')) + list((HERE / 'tests').glob('*'))
    paths += GXTS_SOURCES + [p for p in (ROOT / 'firmware/card_container_v2').glob('*.h')]
    paths += [ROOT / s for s in ['firmware/resident_v2/abi.h', 'firmware/resident_v2/build.py',
              'firmware/engine/core/eng_core.h', 'research/irom_storage/STORAGE_ABI.md',
              'research/tweak_panel_ui/REPORT.md', 'firmware/resident_v2/RESIDENT_SPEC.md']]
    core = ROOT / 'firmware/engine/core'
    paths += [core / s for s in ['eng_data.c','eng_crc_compat.c','eng_semantic.c','eng_pin_stub.c',
              'eng_core.c','eng_grain.c','eng_entries.c','eng_mem.c']]
    paths += list(core.glob('*.h'))
    paths += [ROOT / s for s in ['research/recipe_tweak/r2/tweak_int.c',
              'research/recipe_tweak/r2/tweak_int.h','firmware/card_container_v2/semantic.c']]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths)) if p.is_file()}


if __name__ == '__main__':
    commands = []
    preflight()
    if sys.argv[1:] == ['--sums']:
        sums()
    else:
        before = inputs()
        results = {'host': host(), 'm32r': measure(),
                   'pic_budget': {p: pic_budget(p) for p in ['compact','lto_compact','lto']}}
        (LOCAL / 'pic-budget.json').write_text(json.dumps(results['pic_budget'],indent=2)+'\n')
        after = inputs()
        assert before == after, 'parallel inputs changed during build; this run is not a fixed-input result'
        (LOCAL / 'input-hashes.json').write_text(json.dumps(after, indent=2) + '\n')
        (LOCAL / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        sums()
        best = min(x['core_and_panel_bytes'] for x in results['pic_budget'].values())
        if best > ENGINE_BUDGET:
            print(f'BUDGET FAIL: best core+panel={best} exceeds {ENGINE_BUDGET} by {best-ENGINE_BUDGET}',file=sys.stderr)
            raise SystemExit(2)
