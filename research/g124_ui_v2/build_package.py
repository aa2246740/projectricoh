"""Stage the DAT-only package and compile authoritative C layout offsets."""
from pathlib import Path
import json
import os
import shutil
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

def layout():
    folder = OUT / 'local/layout'
    folder.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    product = TREE / 'candidate/containers/product'
    sets = [
        ('core', 'Engine', product / 'src/firmware/engine/core/eng_core.c',
         ['data.map','stock','ready','recheck','neighbor_valid','epoch','current','confirmed','tweak','confirmed_tweak','list','live','staging','busy',
          'committed','uncertain','stage','confirmed_valid','previewing','write_started','bound']),
        ('adapter', 'Integrated', product / 'adapter.c',
         ['panel','panel.open','panel.input_enabled','panel.recipe','panel.draft','panel.param_index','panel.parameter','panel.list',
          'list','values','lo','hi','failed','watch_view','view_lost','comm_failed','entry','rpc_sequence','failed_text','retry','ui_failed','ui',
          'ui.screen','ui.cur','ui.top','ui.physical','ui.count','ui.slot','ui.param','ui.group','ui.armed','ui.applied_user','ui.levels','ui.saved','ui.text'])]
    reader = load(ROOT / 'tools/native_harness/image_loader.py', 'layout_elf')
    for label, kind, include, fields in sets:
        source = folder / (label + '_layout.c')
        obj = folder / (label + '_layout.o')
        source.write_text('#define ENG_HOST 1\n#include "' + str(include) + '"\n'
            'const unsigned offsets[] __attribute__((section(".layout"),used))={' +
            ','.join('offsetof(' + kind + ',' + f + ')' for f in fields) + ',sizeof(' + kind + ')};\n')
        run([compiler, '-std=c11', '-Os', '-ffreestanding', '-fno-builtin', '-m32r', '-msdata=none', '-G0',
             '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER',
             '-DACCEPTANCE_ENTRIES_HEADER="' + str(TREE / 'candidate/local/product-r13/entries.h') + '"',
             '-c', source, '-o', obj], 'layout-' + label)
        elf = reader.Elf(obj)
        data = next(s['data'] for s in elf.sections if s['name'] == '.layout')
        values = struct.unpack('>' + str(len(fields)+1) + 'I', data)
        save('local/layout/' + ('layout.json' if label == 'core' else 'current-adapter-layout.json'), dict(zip(fields + ['bytes'], values)))

def main():
    built = TREE / 'candidate/local/full-r13'
    raw = (built / 'GXRCE.DAT').read_bytes()
    assert int.from_bytes(raw[28:32], 'big') == 124
    previous = (ROOT / 'firmware/engine_v45_verify/candidate/local/full-r13/effective-rows.bin').read_bytes()
    assert (built / 'effective-rows.bin').read_bytes() == previous
    sd = PACKAGE / 'SD_ROOT'
    shutil.copyfile(built / 'GXRCE.DAT', DAT)
    fixed = ROOT / 'firmware/package_v36_g120b/SD_ROOT'
    assert len(list(sd.iterdir())) == 30
    for path in sd.iterdir():
        if path.name != 'GXRCE.DAT':
            assert path.read_bytes() == (fixed / path.name).read_bytes(), path.name
    (PACKAGE / 'CARD_SHA256SUMS').write_text(''.join(sha(p.read_bytes()) + '  SD_ROOT/' + p.name + '\n' for p in sorted(sd.iterdir())))
    save('evidence/package.json', dict(status='PASS', generation=124, bytes=len(raw), sha256=sha(raw),
         fixed_files=29, resident_unchanged=True, default_effective_rows_unchanged=True, camera_acceptance=False))
    layout()
    print('PASS gen 124 package', len(raw), sha(raw))

if __name__ == '__main__':
    main()
