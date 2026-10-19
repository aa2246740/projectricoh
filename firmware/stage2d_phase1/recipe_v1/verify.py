#!/usr/bin/env python3
"""Run host behavior, independent format checks and M32R compilation locally."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = HERE / 'build'
SAMPLE = ROOT / 'captures/a12-50/2026-10-13/A0-baseline/MYSET01.IFO'
SOURCES = [HERE / name for name in ['recipe_format.c', 'recipe_store.c', 'recipe_apply.c']]
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
BIN = ROOT / 'research/tooling_m32r/prefix/bin'
LINKER = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
CORE = ROOT / 'firmware/recipe_core'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, text=True)
    (BUILD / log).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{command[0]} exit {result.returncode}: {result.stderr}; see {BUILD / log}')
    return result.stdout


def fixture():
    record = SAMPLE.read_bytes()
    if len(record) != 1024 or digest(SAMPLE) != '924591d39ec2f34329bade00efba4783692efdab4cf48844e11586599f3d0431':
        raise ValueError('A0-baseline capture identity mismatch')
    checksum = sum(record[i] * ((i & 15) + 1) for i in range(256, 544)) & 0xffffffff
    if checksum != struct.unpack_from('>I', record, 80)[0]:
        raise ValueError('capture checksum mismatch')
    raw1 = list(record[0x105:0x108] + record[0x152:0x15c])
    raw2 = list(record[0x108:0x10b] + record[0x15c:0x166])
    if raw1 != [8,4,8,2,2,5,5,2,4,4,2,1,3] or raw2 != [6,6,3,7,4,4,4,2,1,5,5,1,4]:
        raise ValueError('real field bytes mismatch')
    wb_raw = [record[0x143], record[0x144]]
    if not all(1 <= b <= 17 for b in wb_raw):
        raise ValueError('capture WB is out of range')
    wb = [b - 9 for b in wb_raw]
    if record[0x104] != 0x03:
        raise ValueError('A0 was Black & White (03), not Standard (01)')
    header = '#ifndef RV1_TEST_FIXTURE_H\n#define RV1_TEST_FIXTURE_H\n'
    for name, values in [('setting1', raw1), ('setting2', raw2)]:
        header += 'static const uint8_t fixture_' + name + '[13] = {' + ','.join(map(str, values)) + '};\n'
    header += 'static const uint8_t fixture_image_selector = 0x03;\n'
    header += 'static const int8_t fixture_wb[2] = {' + ','.join(map(str, wb)) + '};\n#endif\n'
    (BUILD / 'fixture.h').write_text(header)
    result = {'path': str(SAMPLE.relative_to(ROOT)), 'sha256': digest(SAMPLE),
              'checksum': checksum, 'setting1': raw1, 'setting2': raw2,
              'wb_file_offsets': ['0x143', '0x144'], 'wb_raw': wb_raw, 'wb_signed': wb,
              'image_selector': record[0x104], 'image_mode': 'Black & White'}
    (BUILD / 'fixture-provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def inspect_file(path, sample, expected_generation, last_wb=None):
    b = path.read_bytes()
    assert len(b) == 1056
    assert b[:8] == b'GXRRV201'
    assert struct.unpack_from('>HHHH', b, 8) == (2, 32, 64, 16)
    assert struct.unpack_from('>I', b, 16)[0] == expected_generation
    assert struct.unpack_from('>I', b, 20)[0] == 1024
    assert struct.unpack_from('>I', b, 24)[0] == zlib.crc32(b[32:])
    assert struct.unpack_from('>I', b, 28)[0] == zlib.crc32(b[:28])
    for i in range(16):
        p = b[32 + i * 64:32 + (i + 1) * 64]
        assert p[:4] == bytes([i + 1, 1, 3, 4])
        assert p[4:7] == (b'R01' if i % 2 == 0 else b'R02')
        assert p[7:36] == bytes(29)
        assert list(p[36:49]) == sample['setting1' if i % 2 == 0 else 'setting2']
        expected_wb = list(sample['wb_signed'])
        if i == 15 and last_wb is not None:
            expected_wb[0] = last_wb
        assert list(struct.unpack('bb', p[49:51])) == expected_wb
        assert p[51:60] == bytes(9)
        assert struct.unpack_from('>I', p, 60)[0] == zlib.crc32(p[:60])
    return {'path': str(path.relative_to(ROOT)), 'length': len(b), 'sha256': digest(path),
            'generation': expected_generation, 'checked_records': 16}


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    protected = {str(p.relative_to(ROOT)): digest(p) for p in sorted(CORE.rglob('*')) if p.is_file()}
    protected[str(SAMPLE.relative_to(ROOT))] = digest(SAMPLE)
    firmware = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
    protected[str(firmware.relative_to(ROOT))] = digest(firmware)
    baseline_path = HERE / 'protected-inputs.json'
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text())
        if baseline != protected:
            raise ValueError('protected inputs changed since the first run')
    else:
        baseline_path.write_text(json.dumps(protected, indent=2) + '\n')
    sample = fixture()
    common = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-Wpedantic', '-I', HERE, '-I', BUILD]
    cases = []
    for mode, flags in [('host', ['-O2']), ('sanitizers', ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'])]:
        directory = BUILD / (mode + '-files')
        directory.mkdir(exist_ok=True)
        exe = BUILD / ('test-' + mode)
        run(['/usr/bin/clang', *common, *flags, *SOURCES, HERE / 'tests/test_recipe_v1.c', '-o', exe], mode + '-compile.txt')
        output = run([exe, BUILD / (mode + '-golden.bin'), directory,
                      BUILD / (mode + '-applied-S.bin')], mode + '-results.txt')
        passed = [line[5:] for line in output.splitlines() if line.startswith('PASS ') and not line.startswith('PASS total_')]
        if len(passed) < 25:
            raise ValueError('behavior test coverage unexpectedly small')
        cases.append({'mode': mode, 'passed_cases': len(passed), 'cases': passed})
        mode_exe = BUILD / ('test-modes-' + mode)
        run(['/usr/bin/clang', *common, *flags, *SOURCES, HERE / 'tests/test_base_modes.c', '-o', mode_exe],
            mode + '-modes-compile.txt')
        mode_output = run([mode_exe], mode + '-modes-results.txt')
        cases[-1]['base_mode_cases'] = int(re.search(r'RESULT (\d+)', mode_output)[1])

    independent = []
    applied_snapshots = []
    for mode in ['host', 'sanitizers']:
        independent.append(inspect_file(BUILD / (mode + '-golden.bin'), sample, 42))
        independent.append(inspect_file(BUILD / (mode + '-files/RECIPE20.DAT'), sample, 1))
        independent.append(inspect_file(BUILD / (mode + '-files/RECIPE21.DAT'), sample, 2, -8))
        applied = BUILD / (mode + '-applied-S.bin')
        b = applied.read_bytes()
        expected = bytearray((i * 37 + 11) & 255 for i in range(4096))
        # The second real recipe replaces Setting1. Setting2 retains its capture bytes.
        raw = sample['setting2']
        expected[0x36f:0x372] = bytes(raw[:3])
        expected[0x8ac:0x8b6] = bytes(raw[3:])
        expected[0x372:0x375] = bytes(raw[:3])
        expected[0x8b6:0x8c0] = bytes(raw[3:])
        expected[0x6dd:0x6df] = bytes(sample['wb_raw'])
        expected[0x36e] = 0x04
        expected[0x120] = 99
        assert b == expected
        applied_snapshots.append({'path': str(applied.relative_to(ROOT)), 'sha256': digest(applied),
                                  'length': 4096, 'setting1_recipe_from_sample': 'Setting2',
                                  'setting2_preserved': True, 'selector': 4,
                                  'full_4096_byte_comparison': 'PASS'})

    machine = run([GCC, '-dumpmachine'], 'gcc-target.txt').strip()
    if machine != 'm32r-elf':
        raise ValueError(f'wrong target {machine}')
    version = run([GCC, '--version'], 'gcc-version.txt').splitlines()[0]
    flags = ['-std=c11', '-Os', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
             '-fno-common', '-fno-pic', '-m32r', '-mmodel=large', '-Wall', '-Wextra', '-Werror', '-fstack-usage', '-I', HERE]
    objects = []
    for source in SOURCES:
        obj = BUILD / (source.stem + '.m32r.o')
        run([GCC, *flags, '-c', source, '-o', obj], source.stem + '-m32r-compile.txt')
        objects.append(obj)
    obj = BUILD / 'recipe_v1.m32r.o'
    run([LINKER, '-r', *objects, '-o', obj], 'm32r-relocatable-link.txt')
    header = obj.read_bytes()[:52]
    assert header[:6] == b'\x7fELF\x01\x02'
    assert struct.unpack_from('>H', header, 16)[0] == 1
    assert struct.unpack_from('>H', header, 18)[0] == 88
    run([BIN / 'm32r-elf-objdump', '-dr', obj], 'recipe_v1.m32r.disasm.txt')
    headers = run([BIN / 'm32r-elf-objdump', '-h', '-t', obj], 'recipe_v1.m32r.headers.txt')
    undefined = [line for line in headers.splitlines() if '*UND*' in line]
    if undefined:
        raise ValueError(f'undefined symbols: {undefined}')
    sections = {m[1]: int(m[2], 16) for m in re.finditer(
        r'^\s*\d+\s+(\.\S+)\s+([0-9a-f]+)\s+', headers, re.M)}
    (BUILD / 'm32r-size.txt').write_text(json.dumps(sections, indent=2) + '\n')
    # This synthetic VMA tests relocation reach only; it is not a camera code hole.
    layout = BUILD / 'recipe_v1.layout-check.elf'
    run([LINKER, '-e', 'rv1_apply', '-Ttext=0x20400000', obj, '-o', layout], 'm32r-layout-link.txt')
    run([BIN / 'm32r-elf-objdump', '-h', '-t', layout], 'm32r-layout-headers.txt')
    stack = {}
    for p in sorted(BUILD.glob('*.su')):
        for line in p.read_text().splitlines():
            label, n, kind = line.split('\t')
            stack[label.rsplit(':', 1)[-1]] = {'frame_bytes': int(n), 'kind': kind}
    run([GCC, *flags, '-S', HERE / 'tests/abi_probe.c', '-o', BUILD / 'gcc-abi-probe.s'], 'gcc-abi-probe-compile.txt')
    # Const arrays expose target object sizes without running M32R instructions.
    sizes_source = BUILD / 'target_sizes.c'
    sizes_source.write_text('#include "recipe_v1.h"\nconst unsigned char rv1_size_bank[sizeof(Rv1Bank)] = {0};\n'
                            'const unsigned char rv1_size_settings_port[sizeof(Rv1SettingsPort)] = {0};\n'
                            'const unsigned char rv1_size_recipe[sizeof(Rv1Recipe)] = {0};\n')
    run([GCC, *flags, '-c', sizes_source, '-o', BUILD / 'target_sizes.o'], 'target-sizes-compile.txt')
    sizes = run([BIN / 'm32r-elf-objdump', '-t', BUILD / 'target_sizes.o'], 'target-sizes.txt')
    target_sizes = {p[-1]: int(p[-2], 16) for line in sizes.splitlines()
                    if len(p := line.split()) >= 5 and p[-1].startswith('rv1_size_')}
    for path, sha in protected.items():
        if digest(ROOT / path) != sha:
            raise ValueError(f'protected input modified: {path}')
    result = {
        'status': 'PASS', 'sample': sample, 'host_tests': cases,
        'independent_python_zlib_checks': independent,
        'independent_apply_memory_checks': applied_snapshots,
        'm32r': {'compiler': str(GCC.relative_to(ROOT)), 'compiler_version': version,
                  'compiler_sha256': digest(GCC), 'target': machine, 'flags': [str(x) for x in flags],
                  'artifact': str(obj.relative_to(ROOT)), 'artifact_sha256': digest(obj),
                  'artifact_file_bytes': obj.stat().st_size, 'elf_class': 32,
                  'byte_order': 'big', 'elf_machine': 88, 'undefined_symbols': 0,
                  'sections': sections, 'static_stack_frames': stack,
                  'synthetic_vma_link': {'status': 'PASS', 'text_vma': '0x20400000',
                                        'artifact': str(layout.relative_to(ROOT)),
                                        'sha256': digest(layout), 'camera_code_hole_proven': False},
                  'target_sizes': target_sizes},
        'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in
                          [*SOURCES, HERE / 'recipe_v1.h', HERE / 'internal.h', HERE / 'verify.py',
                           HERE / 'tests/test_recipe_v1.c', HERE / 'tests/test_base_modes.c']},
        'protected_inputs_unchanged': True,
        'limits': ['M32R objects were not executed or linked into camera firmware.',
                   'Media faults use a mock adapter; physical SD fault behavior is untested.',
                   'Host stdio close/flush is not a camera durability proof.',
                   'Native file and preview ABI bridges and ADJ hooks are not installed.',
                   'Actual power-off/reboot persistence and module preview are untested.']}
    (BUILD / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'host_cases': [(t['mode'], t['passed_cases']) for t in cases],
                      'm32r_sections': sections, 'target_sizes': target_sizes,
                      'protected_inputs_unchanged': True}, indent=2))


if __name__ == '__main__':
    main()
