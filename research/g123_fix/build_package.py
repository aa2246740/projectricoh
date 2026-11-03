"""Stage the DAT-only card directory and compiler layout evidence."""
from pathlib import Path
import json
import os
import shutil
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, PACKAGE, BASE_DAT, load, save, sha

def layout():
    folder = OUT / 'local/layout'
    folder.mkdir(parents=True,exist_ok=True)
    compiler = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    product = TREE / 'candidate/containers/product'
    sets = [('core', 'Engine', product / 'src/firmware/engine/core/eng_core.c',
             ['data.map','stock','ready','recheck','neighbor_valid','epoch','current','confirmed','tweak','confirmed_tweak','list','live','staging','busy',
              'committed','uncertain','stage','confirmed_valid','previewing','write_started','bound']),
            ('adapter', 'Integrated', product / 'adapter.c',
             ['panel','panel.open','panel.input_enabled','panel.recipe','panel.draft','panel.param_index','panel.parameter','panel.list','list','values','lo','hi',
              'failed','watch_view','view_lost','comm_failed','entry','rpc_sequence','failed_text','retry','ui_failed'])]
    reader = load(ROOT / 'tools/native_harness/image_loader.py', 'layout_elf')
    for label, kind, include, fields in sets:
        source = folder / (label + '_layout.c')
        obj = folder / (label + '_layout.o')
        source.write_text('#define ENG_HOST 1\n#include "' + str(include) + '"\n'
            'const unsigned offsets[] __attribute__((section(".layout"),used))={' +
            ','.join('offsetof(' + kind + ',' + f + ')' for f in fields) + ',sizeof(' + kind + ')};\n')
        command = [str(compiler), '-std=c11', '-Os', '-ffreestanding', '-fno-builtin', '-m32r', '-msdata=none', '-G0',
                   '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER',
                   '-DACCEPTANCE_ENTRIES_HEADER="' + str(TREE / 'candidate/local/product-r13/entries.h') + '"',
                   '-c', str(source), '-o', str(obj)]
        temporary = TREE / 'candidate/local/tmp'
        temporary.mkdir(exist_ok=True)
        result = subprocess.run(command, capture_output=True, text=True,
                                env=dict(os.environ,TMPDIR=str(temporary)))
        (folder / (label + '_compile.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr
        elf = reader.Elf(obj)
        data = next(s['data'] for s in elf.sections if s['name'] == '.layout')
        values = struct.unpack('>' + str(len(fields)+1) + 'I', data)
        record = dict(zip(fields + ['bytes'], values))
        save('local/layout/' + ('layout.json' if label == 'core' else 'current-adapter-layout.json'), record)

def main():
    built = TREE / 'candidate/local/full-r13'
    raw = (built / 'GXRCE.DAT').read_bytes()
    baseline = BASE_DAT.read_bytes()
    assert int.from_bytes(raw[28:32], 'big') == 123
    assert raw[48:112] == baseline[48:112] and raw[212:228] == baseline[212:228]
    assert (built / 'effective-rows.bin').read_bytes() == (ROOT / 'firmware/engine_v42_ux/candidate/local/full-r13/effective-rows.bin').read_bytes()
    sd = PACKAGE / 'SD_ROOT'
    sd.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built / 'GXRCE.DAT', sd / 'GXRCE.DAT')
    assert len(list(sd.iterdir())) == 30
    fixed = ROOT / 'firmware/package_v36_g120b/SD_ROOT'
    for path in sd.iterdir():
        if path.name != 'GXRCE.DAT':
            assert path.read_bytes() == (fixed / path.name).read_bytes(), path.name
    (PACKAGE / 'CARD_SHA256SUMS').write_text(''.join(sha(p.read_bytes()) + '  SD_ROOT/' + p.name + '\n' for p in sorted(sd.iterdir())))
    save('package.json', dict(status='PASS', generation=123, bytes=len(raw), sha256=sha(raw),
         card_files=[p.name for p in sorted(sd.iterdir())], resident_unchanged=True, effective_rows_unchanged=True,
         resident_build_id=raw[80:112].hex(), camera_acceptance=False))
    layout()
    print('PASS gen 123 DAT-only package', sha(raw), len(raw), flush=True)

if __name__ == '__main__':
    main()
