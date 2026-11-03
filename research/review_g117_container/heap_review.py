"""Measure M32R ABI sizes; model only allocations that still execute in 117."""
from pathlib import Path
import importlib.util
import json
import struct
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CAND = OUT / 'isolated/candidate'
sys.path.insert(0, str(CAND))
import common as c
build = c.load(c.PRODUCT / 'build.py', 'target_heap_profile')
obj = OUT / 'layout-m32r.o'
c.run([c.GCC, *build.FLAGS, '-DPN_CORE_HEADER="../core/eng_core.h"', '-DPN_GXTS_SHARED_PARAMETER',
       '-I', c.PRODUCT, '-I', c.RESIDENT, '-c', c.HERE / 'layout.c', '-o', obj], 'review-target-layout')
reader = c.load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'target_heap_elf')
elf = reader.Elf(obj)
symbol = elf.symbols['v33_target_sizes']
section = elf.sections[symbol['section']]
start = symbol['value'] - section['va']
data = elf.content(section)[start:start + symbol['size']]
sizes = dict(zip(('SessionWork', 'PnGxts', 'PsStore', 'RvLoadWork', 'RvUiSnapshot', 'Integrated', 'RvSession', 'RV_BLOCK_OVERHEAD'), struct.unpack('>8I', data)))
assert sizes['RvLoadWork'] == 608 and sizes['SessionWork'] == 1460 and sizes['RV_BLOCK_OVERHEAD'] == 7504
raw = (CAND / 'local/full-r13/GXRCE.DAT').read_bytes()
main = sizes['RV_BLOCK_OVERHEAD'] + ((len(raw) + struct.unpack_from('>I', raw, 116)[0] + 3) & ~3)
requests = [sizes['RvLoadWork'], main, sizes['SessionWork'], sizes['RvUiSnapshot']]
assert requests == [608, 72656, 1460, 1968]
old = json.loads((ROOT / 'firmware/engine_v36_r28/local/evidence-v34c/heap.json').read_text())
assert old['sizes'] == sizes and old['main_request'] == 84276
assert old['steady_with_all_optional_allocations'] == 88360
result = dict(status='PASS_M32R_LAYOUT_AND_HOST_ALLOCATIONS_MODEL', sizes=sizes,
              gen117_requests=requests, gen117_native_header_each=12,
              gen117_steady_including_four_headers=sum(requests) + 4 * 12,
              gen117_install_buffers=[],
              gen115_main_request=84276, gen115_first_install_with_headers=216004,
              gen115_install_with_existing_ui=217984, gen115_steady_with_optional=88360,
              steady_reduction_vs_gen115=88360 - (sum(requests) + 4 * 12),
              host64_trace=[616, 72656, 1512, 1968],
              live_camera_heap_or_fragmentation_measured=False)
(OUT / 'heap-results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
