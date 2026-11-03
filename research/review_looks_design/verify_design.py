#!/usr/bin/python3
"""Recheck the design inputs, budgets, and native allocator observations offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_looks_design'
DESIGN = ROOT / 'research/looks_expansion_design'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-looks')
BEGIN = 0x20704800
CAPACITY = 262144
KINDS = (0, 1, 2, 3, 0, 1, 1, 1, 0, 1)
LENGTHS = (62, 33, 96, 56)


def u16(data, off):
    return struct.unpack_from('>H', data, off)[0]


def u32(data, off):
    return struct.unpack_from('>I', data, off)[0]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def align4(value):
    return (value + 3) & ~3


def area(k):
    return 32 + 32*k + align4(62*((k+3)//4)) + align4(33*((3*k+1)//2)) + 152*k


def check_inputs():
    found = []
    for line in (DESIGN / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(None, 1)
        p = (DESIGN / name.lstrip('*')).resolve()
        assert p.is_relative_to(DESIGN)
        data = p.read_bytes()
        assert sha(data) == digest, name
        found.append({'path': str(p.relative_to(ROOT)), 'bytes': len(data), 'sha256': digest})
    assert len(found) == 10
    return found


def check_data():
    datpath = ROOT / 'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT'
    data = datpath.read_bytes()
    shared = u32(data, 192)
    pools = [{'kind': k, 'count': u16(data, shared+16+12*k),
              'bytes_per_row': u16(data, shared+18+12*k)} for k in range(4)]
    modules = []
    for m in range(3):
        directory = u32(data, 156) + 64*m
        table, bank = u32(data, directory+20), u32(data, directory+16)
        entries = []
        for i in range(data[directory+30]):
            entry = data[table+16+20*i:table+36+20*i]
            rows = []
            for j, kind in enumerate(KINDS):
                head = shared + 16 + 12*kind
                start = shared + u32(data, head+4) + entry[8+j]*LENGTHS[kind]
                rows.append(data[start:start+LENGTHS[kind]])
            slot = entry[0]
            record = data[bank+32+(slot-1)*64:bank+32+slot*64]
            if slot != 4:
                assert rows[0] == rows[8] and rows[1] == rows[9]
            entries.append({'slot': slot, 'flags': entry[1], 'indices': list(entry[8:18]),
                            's_mode': record[3], 's_colour_wb_hex': record[36:51].hex(),
                            'colour_all_zero': not any(rows[2])})
        modules.append({'index': m, 'entries': entries})
    assert [p['count'] for p in pools] == [7, 13, 10, 8]
    assert sum(p['count']*p['bytes_per_row'] for p in pools) == 2271
    for m in modules:
        assert all(e['s_mode'] == 1 and int(e['s_colour_wb_hex'], 16) == 0 for e in m['entries'])
    layouts = {}
    for gen, tree in ((137, 'engine_v54_g137'), (139, 'engine_v56_g139'),
                      (149, 'engine_v58_g149'), (150, 'engine_v58_g150')):
        p = ROOT / 'firmware' / tree / 'candidate/local/full-r13/layout.json'
        doc = json.loads(p.read_text())
        layouts[gen] = {key: doc[key] for key in ('file_bytes', 'bss_bytes', 'engine_bytes')}
        overhead = 7628 if gen == 149 else 7504
        layouts[gen]['block_overhead'] = overhead
        layouts[gen]['main_request'] = overhead + align4(doc['file_bytes'] + doc['bss_bytes'])
    budgets = []
    for code in (2120, 2650, 3180):
        for label, extra_file, extra_bss in (('g150', 0, 0), ('g150_v39', 1124, 28)):
            options = []
            for k in range(49):
                file_bytes = 87464 + code + 16 + area(k) + extra_file
                overhead = 7628 if extra_file else 7504
                main = overhead + align4(file_bytes + 9152 + 40 + 20 + extra_bss)
                if file_bytes <= 98304:
                    options.append((k, file_bytes, main))
            k, size, main = options[-1]
            reserved = [row for row in options if row[1] <= 98304-512][-1]
            budgets.append(dict(code=code, base=label, capacity=k, file_bytes=size, main_request=main,
                                file_margin=98304-size, capacity_with_512_margin=reserved[0]))
    return dict(dat_sha256=sha(data), dat_bytes=len(data), pools=pools, modules=modules,
                layouts=layouts, budgets=budgets, area_sizes={k: area(k) for k in (6,10,16,24,28,30,32,36)},
                minimum_safe_effect=33+96+56+32, t1_effect=33+96+56+32+66,
                full_gate=139320-77336-8192, partial_gate=139320-77336,
                partial_request_at_61984=261512-61984-85528)


def native_checks(scratch):
    sys.path.insert(0, str(ROOT / 'tools/native_harness'))
    import python_backend as backend
    from image_loader import Image, OFFICIAL, PINS
    backend.CACHE = scratch / 'decode'
    image = Image(OFFICIAL, PINS['official'])
    image.verify_csv()
    body_comparisons = []
    windows = ((0x2005bf00, 0x2005c108), (0x200bbd98, 0x200bbf4c), (0x200da69c, 0x200da6c8))
    for name in ('firmware/package_v38_g150/local/SD_ROOT/ilaunch3',
                 'firmware/package_v39_g149/local/SD_ROOT/ilaunch3'):
        candidate = Image(ROOT / name)
        same = all(candidate.bytes_at(a, z-a) == image.bytes_at(a, z-a) for a, z in windows)
        assert same, name
        body_comparisons.append({'path': name, 'sha256': candidate.sha256, 'native_windows_equal': same})
    calls = []

    def make(request):
        b = backend.PythonBackend()
        image.load(b)
        b.map(0x206e0000, bytes(0x20000))
        b.map(BEGIN, bytes(CAPACITY+12))
        b.set_reg('r15', 0x206ffff0)
        def call(address, arg=None):
            if arg is not None:
                b.set_reg('r4', arg)
            stop = b.call(address, (), 0x0bad0000, 2000000)
            assert stop.reason == 'return', (address, stop)
            calls.append({'pc': hex(address), 'arg': arg, 'steps': stop.steps, 'result': b.get_reg('r0')})
            return b.get_reg('r0')
        assert u32(b.read(0x200c0dc0, 8), 0) == BEGIN
        assert u32(b.read(0x200c0dc0, 8), 4) == CAPACITY
        call(0x200bbd98)
        assert call(0x2005bf5c, 608)
        assert call(0x2005bf5c, request)
        first = u32(b.read(BEGIN, 4), 0)
        assert u32(b.read(first+8, 4), 0) == 261512-request
        return b, call, first

    b, call, first = make(122192)
    snapshots = []
    for label in ('initial', 'warm', 'repeat'):
        if label != 'initial':
            p = call(0x200bbe00, 77312)
            assert p
            call(0x200bbf20, p)
        raw = b.read(BEGIN, CAPACITY+12)
        (scratch / (label+'.bin')).write_bytes(raw)
        snapshots.append({'name': label, 'sha256': sha(raw)})
    assert (scratch/'warm.bin').read_bytes() == (scratch/'repeat.bin').read_bytes()
    for label in ('two_warm', 'two_repeat'):
        pointers = [call(0x200bbe00, size) for size in (32768, 77312)]
        assert all(pointers)
        for p in reversed(pointers):
            call(0x200bbf20, p)
        raw = b.read(BEGIN, CAPACITY+12)
        (scratch / (label+'.bin')).write_bytes(raw)
        snapshots.append({'name': label, 'sha256': sha(raw)})
    assert (scratch/'two_warm.bin').read_bytes() == (scratch/'two_repeat.bin').read_bytes()
    pressures = []
    null_path = None
    for request in (108124, 122192):
        b, call, free_at = make(request)
        steps = []
        for size in (32768, 16384, 938, 77312, 4608, 12368):
            pointer = call(0x200bbe00, size)
            steps.append({'request': size, 'pointer': hex(pointer), 'success': bool(pointer)})
        pressures.append({'main_request': request, 'steps': steps})
        if request == 122192:
            b.set_reg('r4', 0)
            stop = b.call(0x200da69c, (), 0x0bad0000, 2000000)
            null_path = {'entry': '0x200da69c', 'reason': stop.reason,
                         'pc': hex(stop.pc), 'steps': stop.steps, 'detail': stop.detail}
            assert stop.reason == 'fault' and 'unmapped memory 0x0/' in stop.detail, null_path
    assert all(s['success'] for s in pressures[0]['steps'])
    assert not pressures[1]['steps'][-1]['success']
    return {'body_sha256': image.sha256, 'first_free_offset': first-BEGIN, 'snapshots': snapshots,
            'body_comparisons': body_comparisons,
            'pressure_comparison': pressures, 'null_path': null_path, 'calls': calls}


HEAP_DRIVER = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char memory[262156];
static uint32_t word(uint32_t address) {
    size_t off=address-0x20704800u;
    if(off+4>sizeof(memory)) abort();
    return (uint32_t)memory[off]<<24 | (uint32_t)memory[off+1]<<16 |
           (uint32_t)memory[off+2]<<8 | memory[off+3];
}
#define RV_PTR(a) (memory+(uint32_t)(a)-0x20704800u)
#define RV_WORD(a) word(a)
#include "p_heapmark.c"
static void read_file(const char *path) {
    FILE *f=fopen(path,"rb");
    if(!f || fread(memory,1,sizeof(memory),f)!=sizeof(memory)) abort();
    fclose(f);
}
int main(int argc,char **argv) {
    if(argc!=4) return 2;
    uint32_t first=(uint32_t)strtoul(argv[3],0,10)+0x20704800u;
    read_file(argv[1]);
    if(hm_baseline(0x20704800u,0x20744800u,0x20704800u,first)) return 3;
    read_file(argv[2]);
    if(hm_read(139320,139320,0,1)) return 4;
    uint32_t peak=hm_hist[0].hi>first?hm_hist[0].hi-first:0;
    printf("{\"changed\":%u,\"peak\":%u,\"verdict\":%d}\n",
           hm_hist[0].changed,peak,hm_verdict(first,139320,77336,8192));
    return 0;
}
'''


def prototype_checks(scratch, native):
    src = scratch / 'heap_driver.c'
    binary = scratch / 'heap_driver'
    src.write_text(HEAP_DRIVER)
    env = os.environ.copy()
    env['TMPDIR'] = str(scratch)
    env['CLANG_MODULE_CACHE_PATH'] = str(scratch / 'clang-cache')
    subprocess.run(['/usr/bin/clang', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-I'+str(DESIGN/'prototype'), str(src), '-o', str(binary)],
                   env=env, check=True, capture_output=True, text=True)
    results = []
    for before, after in (('initial', 'warm'), ('warm', 'repeat'),
                          ('two_warm', 'two_repeat'), ('repeat', 'repeat')):
        p = subprocess.run([str(binary), str(scratch/(before+'.bin')), str(scratch/(after+'.bin')),
                            str(native['first_free_offset'])], env=env, check=True,
                           capture_output=True, text=True)
        results.append({'before': before, 'after': after, **json.loads(p.stdout)})
    assert results[0]['peak'] >= 77336 and results[0]['verdict'] == 0
    assert results[1]['changed'] == 0 and results[1]['peak'] == 0 and results[1]['verdict'] == 1
    return results


def target_layout_checks(scratch):
    env = os.environ.copy()
    env['TMPDIR'] = str(scratch)
    compiler = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    dumper = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    results = []
    for version in ('v38', 'v39'):
        source = scratch / (version+'_layout.c')
        obj = scratch / (version+'_layout.o')
        header = ROOT / 'firmware' / ('resident_'+version) / 'resident/resident.h'
        source.write_text('#include "'+str(header)+'"\n'
                          'const uint32_t review_sizes[]={sizeof(RvSession),RV_BLOCK_OVERHEAD,RV_MAX_BLOCK_BYTES};\n')
        subprocess.run([str(compiler), '-std=c11', '-Oz', '-ffreestanding', '-m32r', '-c',
                        str(source), '-o', str(obj)], env=env, check=True, capture_output=True, text=True)
        result = subprocess.run([str(dumper), '-s', '-j', '.rodata', str(obj)], env=env,
                                check=True, capture_output=True, text=True)
        raw = bytearray()
        for line in result.stdout.splitlines():
            bits = line.split()
            if len(bits)>1 and bits[0] == '0000':
                raw.extend(bytes.fromhex(''.join(bits[1:4])))
        assert len(raw) == 12, result.stdout
        session, overhead, maximum = struct.unpack('>3I', raw)
        results.append({'version': version, 'header_sha256': sha(header.read_bytes()),
                        'session_bytes': session, 'block_overhead': overhead, 'maximum_main_request': maximum,
                        'free_at_maximum': 261512-maximum})
    assert results[0]['block_overhead'] == 7504 and results[1]['block_overhead'] == 7628
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT/'checks.json')
    args = parser.parse_args()
    dest = args.output.resolve()
    assert dest.is_relative_to(OUT) or dest.is_relative_to(SCRATCH)
    volume = subprocess.run(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace'],
                            check=True, capture_output=True)
    info = plistlib.loads(volume.stdout)
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume']
    assert not SCRATCH.is_symlink()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    output = {'evidence': 'Host arithmetic, native allocator instruction replay, and original C prototype. No device run.',
              'runner_notes': [
                  'The first run stopped because its row14=row5 assertion also covered stock 04. The corrected assertion covers non-04 recipes only.',
                  'The first NULL-path check expected a four-byte store at zero. The native clear routine actually attempts a one-byte store at zero. The corrected assertion checks the address.'],
              'inputs': check_inputs(), 'data': check_data()}
    print('Input and data checks complete.', flush=True)
    output['native'] = native_checks(SCRATCH)
    print('Native allocator checks complete.', flush=True)
    output['heap_prototype'] = prototype_checks(SCRATCH, output['native'])
    output['target_layouts'] = target_layout_checks(SCRATCH)
    dest.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(dest), 'heap_prototype': output['heap_prototype'],
                      'data_sha256': output['data']['dat_sha256']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
