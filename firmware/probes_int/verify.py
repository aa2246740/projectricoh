#!/usr/bin/env python3
"""Run the real resident loader and services with portable probe entry dispatch."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pi_verify_support', HERE / 'support.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def main():
    s.preflight()
    r = s.UPSTREAM / 'resident_slim'
    out = s.LOCAL / 'tests'
    out.mkdir(exist_ok=True)
    common = ['clang', '-std=c11', '-O1', '-g', '-fno-builtin', '-fno-common', '-Wall', '-Wextra',
              '-Werror', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
              '-DRV_HOST', '-DPV_HOST', '-I', HERE, '-I', r]
    objects = []
    sources = ['resident.c', 'loader.c', 'shared.c', 'runtime.c', 'validate_envelope.inc.c',
               'engine_services/services.c', 'engine_services/api.c', 'shared.c@engine',
               'runtime.c@engine', 'engine_services/crc.c', 'local/trust.c']
    for name in sources:
        source = r / name.split('@')[0]
        obj = out / (name.replace('/', '-').replace('@', '-') + '.o')
        options = []
        if name == 'runtime.c':
            options += ['-Dmemcpy=rv_test_memcpy', '-Dmemset=rv_test_memset']
        if name == 'runtime.c@engine':
            options += ['-Dmemcpy=es_test_memcpy', '-Dmemset=es_test_memset']
        if name.endswith('@engine') or name.startswith('engine_services/'):
            options += ['-DRV_ENGINE_SERVICES']
        if name == 'engine_services/api.c':
            options += ['-Drv_service=pi_observe_service']
        s.run([*common, *options, '-c', source, '-o', obj], 'host-compile-' + obj.stem)
        objects.append(obj)
    decoder = s.module(HERE / 'decode.py', 'pi_decoder')
    results = {}
    python_checks = 0

    def check(value, message):
        nonlocal python_checks
        python_checks += 1
        if not value:
            raise AssertionError(message)

    def reject(text, message):
        try:
            decoder.decode_text(text)
        except ValueError:
            check(True, message)
        else:
            check(False, message)

    for number, name, witness in [(1, 'life', 65536), (2, 'notice', 65536), (3, 'view', 65536),
                                   (1, 'life', 256), (1, 'life', 32768)]:
        label = f'{name}-{witness}'
        binary = out / label
        own = []
        for source in ('engine.c', 'host_checks.c'):
            obj = out / (label + '-' + source + '.o')
            s.run([*common, f'-DPV_ENGINE={number}', f'-DPV_WITNESS_BYTES={witness}', '-c',
                   HERE / source, '-o', obj], 'host-compile-' + label + '-' + source)
            own.append(obj)
        s.run(['clang', '-fsanitize=address,undefined', *objects, *own, '-o', binary], 'host-link-' + label)
        rows = out / (label + '-rows.txt')
        candidate = s.LOCAL / ('witness-tiers' if number == 1 and witness != 65536 else 'candidates') / (label if number == 1 and witness != 65536 else name) / 'GXRCE.DAT'
        result = s.run([binary, candidate, rows], 'host-run-' + label)
        info = json.loads(result.stdout)
        info['candidate_path'] = str(candidate.relative_to(HERE))
        info['candidate_sha256'] = s.sha(candidate)
        check(info['writes'] == info['rpc_calls'] == info['forbidden_calls'] == 0, 'readonly runtime')
        check(info['m32r_executed'] is False, 'host execution must remain explicitly labelled')
        captures = decoder.decode_text(rows.read_text())['captures']
        check(len(captures) == info['captures'] and all(c['verified'] for c in captures), 'codec roundtrip')
        expected = [(1 << 24) | (number << 16) | (2 << 8) | 3, 7, 73]
        expected += [0x10203040 + i for i in range(12)]
        expected += [zlib.crc32(struct.pack('>15I', *expected))]
        check([int(captures[0]['words'][f'{i:02X}'], 16) for i in range(16)] == expected, 'independent golden word/CRC order')
        page_count = 17 if number == 1 else 12
        for unit in range(3):
            pages = captures[1 + page_count * unit:1 + page_count * (unit + 1)]
            check([c['page'] for c in pages] == list(range(page_count)), 'all encoded pages for each unit')
            if number == 1:
                check(pages[3]['fields']['bytes'] == witness, 'witness tier')
                check([pages[i]['largest_successful_tier_kib'] for i in (5, 6, 7)] == [48, 40, 32], 'three timings')
                check(all(pages[i]['capacity_complete'] for i in (5, 6, 7)), 'capacity free completeness')
                check(pages[14]['fields']['free_header_detail_1'] == 0x100, 'free success is header flag, not native return')
            elif number == 2:
                check(pages[3]['unit_name_ascii'] == ('jlaunch', 'qlaunch', 'l08firm')[unit], 'full unit identity')
            else:
                check(pages[2]['fields']['axis_order'] == 0xffffffff, 'unknown WB axes stay unknown')
        golden_lines = rows.read_text().splitlines()[:16]
        damaged = golden_lines.copy()
        damaged[5] = damaged[5][:4] + f'{int(damaged[5][4:], 16) ^ 1:08X}'
        reject('\n'.join(damaged), 'CRC corruption rejected')
        reject('\n'.join(golden_lines[:5] + golden_lines[6:]), 'missing row rejected')
        reject('\n'.join(golden_lines + [golden_lines[5]]), 'duplicate row rejected')
        partial = decoder.decode_text('\n'.join(golden_lines[:5]), partial=True)['captures'][0]
        check(not partial['verified'], 'partial data cannot pass')
        ocr = '\n'.join(line[:4] + line[4:].replace('0', 'O') for line in golden_lines)
        reject(ocr, 'OCR corrections must be explicit')
        check(decoder.decode_text(ocr, ocr=True)['captures'][0]['verified'], 'explicit OCR correction with CRC')
        cli = s.run(['python3', '-I', '-B', HERE / 'decode.py', rows], 'decode-' + label)
        s.save(out / (label + '-decoded.json'), json.loads(cli.stdout))
        results[label] = info
        print(f'{label}: checks={info["checks"]} captures={info["captures"]} forbidden=0')
    s.save(out / 'commands.json', s.COMMANDS)
    s.save(out / 'summary.json', dict(status='PASS', engines=results, python_checks=python_checks,
                                     c_checks=sum(r['checks'] for r in results.values()),
                                     sanitizer='ASan + UBSan', resident_loader=True, real_service_sources=True,
                                     native_m32r_execution=False, native_renderer_tested=False,
                                     host_sources={n:s.sha(HERE/n) for n in ('engine.c','probes.h','host_checks.c','verify.py')},
                                     camera_acceptance=False))
    print(f'PASS python_checks={python_checks} host_loader=1 native_m32r=0 camera=0')


if __name__ == '__main__':
    main()
