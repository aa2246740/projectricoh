"""Confirm that the cache oracle distinguishes the earlier DAT."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_review as br
rs = br.rs


def main():
    started = time.monotonic()
    os.environ['CPUPROBE_OLD_BUILD'] = '1'
    cp = br.prepare('old-cache', '50mm')
    s = cp.Session('50mm')
    old_source = (br.SOURCE / 'local/old-src/probe-reviewed.c').read_text()
    old_source = old_source.replace('"../../engine_services/engine_services.h"',
        '"' + str(cp.PRODUCT.parents[1] / 'engine_services/engine_services.h') + '"')
    old_source = old_source.replace('"kernel.h"', '"' + str(cp.PRODUCT / 'kernel.h') + '"')
    fields = ['offsetof(Probe,%s)' % name for name in cp.FIELDS]
    fields += ['sizeof(Test)']
    fields += ['offsetof(Test,%s)' % name for name in cp.TEST_FIELDS]
    work = rs.TEMP / 'old-layout'
    work.mkdir(parents=True, exist_ok=True)
    src = work / 'layout.c'
    src.write_text(old_source + '\nconst uint32_t probe_offsets[]={' + ','.join(fields) + '};\n')
    gcc = rs.ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    obj = work / 'layout.o'
    subprocess.run([str(gcc), '-std=c11', '-Os', '-ffreestanding', '-fpic', '-m32r', '-mmodel=medium',
                    '-msdata=none', '-G0', '-fno-builtin', '-c', str(src), '-o', str(obj)],
                    check=True, cwd=rs.ROOT, timeout=600)
    reader = cp.load(rs.ROOT / 'firmware/stage2l_switch/tools/build.py', 'old_layout_reader')
    elf = reader.Elf(obj)
    symbol = elf.symbols['probe_offsets']
    count = len(fields)
    raw = elf.content(elf.sections[symbol['section']])
    values = struct.unpack('>%dI' % count, raw[symbol['value']:symbol['value'] + 4 * count])
    old = dict(zip(cp.FIELDS, values[:len(cp.FIELDS)]))
    old['test_size'] = values[len(cp.FIELDS)]
    old['Test'] = dict(zip(cp.TEST_FIELDS, values[len(cp.FIELDS) + 1:]))
    assert old == s.off, (old, s.off)
    s.engine_writes = br.WriteCounts()
    report = dict(case='old-cache', unit='50mm', dat=rs.digest(cp.DAT),
                  common_layout_equal=True, backend='tools/gxr_emulator_batch')
    try:
        cp.case_cache(s, report)
        cp.final_audit(s, report)
        assert len(report['cache_cases']) == 22
        assert len(report['old_build_cases_failing']) == 19, report['old_build_cases_failing']
        report['status'] = 'CONTROL_REPRODUCED'
    finally:
        report['seconds'] = round(time.monotonic() - started, 3)
        report['batch_stats'] = dict(s.h.b.batch_stats)
        rs.save(cp.HERE / 'result.json', report)
        print('OLD_CONTROL', report.get('status', 'FAIL'), report['seconds'], flush=True)


if __name__ == '__main__':
    main()
