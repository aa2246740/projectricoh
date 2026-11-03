"""Run the retained instruction-derived math checker on a fresh g138 model.

This is a host-driven compute check. The saved RAM is a private model input,
not a physical cold boot or an accepted RTOS checkpoint.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import struct
import sys
import types

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT))
import g138_host as H
import knob_ranges as K

parser = argparse.ArgumentParser()
parser.add_argument('--unit', choices=['50mm', '28mm', 'mount'], required=True)
args = parser.parse_args()
unit = H.UNITS[args.unit]
job = os.environ.get('REVIEW_JOB', 'direct-' + str(os.getpid()))
assert re.fullmatch(r'[A-Za-z0-9_-]+', job), job
WORK = OUT / 'local/target-math' / (args.unit + '-' + job)
WORK.mkdir(parents=True, exist_ok=True)
source = ROOT / 'research/g135_v37'
inputs = [source / 'target_check.py', source / 'target_runner.c', source / 'local' / ('target-cases-%d.bin' % unit),
          H.ENGINE, ROOT / 'firmware/engine_v55_g138/candidate/local/logs/m32r-lto-oz-disassembly.log',
          ROOT / 'research/kv2_math/test_target.py']
frozen = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
(WORK / 'inputs-before.json').write_text(json.dumps(frozen, indent=2) + '\n')
dat = H.DAT.read_bytes()
records = inputs[2].read_bytes()
assert len(records) % 580 == 0
observed = Counter()
reference_output = {}
for offset in range(0, len(records), 580):
    selected_unit, slot = struct.unpack_from('>II', records, offset)
    assert selected_unit == unit
    key = (slot, struct.unpack_from('>10h', records, offset + 8))
    observed[key] += 1
    output = records[offset+28:offset+580]
    assert key not in reference_output or reference_output[key] == output
    reference_output[key] = output
wanted = Counter()
for slot in range(1, 9):
    for item in K.items(dat, unit, slot):
        for level in item['levels']:
            values = [100] + [0] * 9
            values[item['control']] = level
            wanted[(slot, tuple(values))] += 1
assert observed == wanted, 'Frozen reference vectors do not cover the current selectable points'
directory = struct.unpack_from('>I', dat, 156)[0] + 64 * unit
mapping = struct.unpack_from('>I', dat, directory+12)[0]
owned = [(struct.unpack_from('>H', dat, mapping+32+12*row+6)[0],
          struct.unpack_from('>H', dat, mapping+32+12*row+4)[0]) for row in range(9)]
applied_bytes = sum(count for _, count in owned) + 2
assert applied_bytes == 505


def applied(value):
    return b''.join(value[offset:offset+count] for offset, count in owned) + value[445:447]


aliases = []
adjacent_pairs = 0
for slot in range(1, 9):
    for item in K.items(dat, unit, slot):
        previous = None
        for level in item['levels']:
            values = [100] + [0] * 9
            values[item['control']] = level
            signature = applied(reference_output[(slot, tuple(values))])
            if previous is not None:
                adjacent_pairs += 1
                if signature == previous[1]:
                    aliases.append(dict(slot=slot, control=item['control'], levels=[previous[0], level]))
            previous = (level, signature)
H.setup()
cam = H.Camera(args.unit)
cam.open_menu()
state = WORK / 'state'
state.mkdir(exist_ok=True)
regions = []
for index, (base, data, writable) in enumerate(cam.h.b.regions):
    filename = 'region-%03d.bin' % index
    (state / filename).write_bytes(bytes(data))
    regions.append(dict(base=base, bytes=len(data), writable=writable, file=filename))
(state / 'state.json').write_text(json.dumps(dict(regions=regions, source='fresh g138 host model after H01',
                                               actual_camera_boot=False), indent=2) + '\n')
shutil.copyfile(source / 'target_runner.c', WORK / 'target_runner.c')
(WORK / 'local').mkdir(exist_ok=True)
shutil.copyfile(source / 'local' / ('target-cases-%d.bin' % unit), WORK / 'local' / ('target-cases-%d.bin' % unit))


def check_inputs():
    assert H.sha(H.DAT) == '88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a'
    assert H.sha(H.BODY) == H.BODY_SHA
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in frozen.items())


fence = types.ModuleType('fences')
fence.ROOT, fence.WORK = ROOT, WORK
fence.ENGINE = ROOT / 'firmware/engine_v55_g138'
fence.enable, fence.check_inputs = H.setup, check_inputs
sys.modules['fences'] = fence
spec = importlib.util.spec_from_file_location('g138_target_math_checker', source / 'target_check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def locate_current(regions, image_dat):
    # g138 adds a nonzero-initialized writable word inside the loaded image.
    # Keep the actual RAM unchanged; normalize only that ELF symbol for the
    # retained checker's immutable-image identity comparison.
    image = cam.p.image_base
    elf_type = runpy.run_path(str(ROOT / 'firmware/stage2l_switch/tools/build.py'))['Elf']
    seen = elf_type(H.ENGINE).symbols['t_seen']
    assert seen['size'] == 4
    offset = seen['value']
    assert cam.symbol('t_seen') == image + offset
    current = bytearray(cam.h.b.read(image, len(image_dat)))
    assert current[:256] == image_dat[:256]
    assert int.from_bytes(current[offset:offset+4], 'big') == 2
    assert int.from_bytes(image_dat[offset:offset+4], 'big', signed=True) == -1
    relocation_at, relocation_bytes = struct.unpack_from('>II', image_dat, 144)
    for at in range(relocation_at, relocation_at+relocation_bytes, 8):
        patch, target = struct.unpack_from('>II', image_dat, at)
        assert struct.unpack_from('>I', current, patch)[0] == image + target
        struct.pack_into('>I', current, patch, target)
    differences = [i for i, (a, b) in enumerate(zip(current, image_dat)) if a != b]
    assert differences == list(range(offset, offset+4)), differences
    current[offset:offset+4] = image_dat[offset:offset+4]
    assert bytes(current) == image_dat
    # The original locator still checks every byte and every relocation.
    # Replace only the identity copy of the one region, never the backend.
    identity_regions = []
    containing = 0
    for base, data, writable in regions:
        if base <= image and image+len(image_dat) <= base+len(data):
            copied = bytearray(data)
            start = image-base+offset
            assert copied[start:start+4] == cam.h.b.read(image+offset, 4)
            copied[start:start+4] = image_dat[offset:offset+4]
            data = bytes(copied)
            containing += 1
        identity_regions.append((base, data, writable))
    assert containing == 1
    located = retained_locate(identity_regions, image_dat)
    assert located == image
    binding = dict(status='PASS_IMAGE_IDENTITY', image_address=image,
                   dat_sha256=hashlib.sha256(image_dat).hexdigest(),
                   normalized_sha256=hashlib.sha256(current).hexdigest(),
                   mutable_symbol='t_seen', mutable_symbol_rva=offset, mutable_bytes=4,
                   post_H01_value=2, normalized_difference_offsets=differences,
                   runtime_RAM_modified=False)
    (WORK / 'identity-binding.json').write_text(json.dumps(binding, indent=2) + '\n')
    return image


retained_locate = module.locate
module.locate = locate_current
sys.argv = [str(source / 'target_check.py'), '--state', str(state), '--unit', str(unit)]
module.main()
result = json.loads((WORK / ('target-%d.json' % unit)).read_text())
result.update(scope='M32R-derived C execution plus direct interpreter samples; host-driven compute only',
              state_source='fresh H01 host model', actual_camera_boot=False,
              reference_covers_all_current_single_control_points=True,
              applied_projection_bytes=applied_bytes, adjacent_applied_pairs=adjacent_pairs,
              equal_adjacent_applied_outputs=len(aliases), applied_aliases=aliases,
              identity_binding=str((WORK / 'identity-binding.json').relative_to(OUT)),
              checker_sha256=frozen[str((source / 'target_check.py').relative_to(ROOT))])
if aliases:
    result['status'] = 'FAIL_APPLIED_NEIGHBORS'
(OUT / 'evidence' / ('target-math-' + args.unit + '.json')).write_text(json.dumps(result, indent=2) + '\n')
check_inputs()
assert not aliases, ('adjacent points have the same nine rows and T', aliases)
