"""Compare every selectable level with the previous, separate-buffer engine."""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import knob_ranges as K

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
K.TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138/borrow-current')
current = K.build()
K.PRODUCT = ROOT / 'firmware/engine_v54_g137/candidate/containers/product'
K.TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138/borrow-previous')
previous = K.build()
new_dat = K.DAT.read_bytes()
old_dat = (ROOT / 'firmware/package_v38_g137/SD_ROOT/GXRCE.DAT').read_bytes()
new_memory = (ct.c_uint8 * len(new_dat)).from_buffer_copy(new_dat)
old_memory = (ct.c_uint8 * len(old_dat)).from_buffer_copy(old_dat)
points = adjacent_equal = comparisons = 0
digest = hashlib.sha256()
for unit in range(3):
    assert current.g135_open(new_memory, len(new_dat), unit) == 0
    assert previous.g135_open(old_memory, len(old_dat), unit) == 0
    cases = []
    for slot in range(1, 9):
        default = K.Levels()
        assert current.g135_default(slot, ct.byref(default)) == 0
        for item in K.items(new_dat, unit, slot):
            outputs = {}
            for level in item['levels']:
                values = list(default.v)
                values[item['control']] = level
                cases.append((slot, values))
                value = K.Levels((ct.c_int16 * 10)(*values))
                new_out, old_out = (ct.c_uint8 * 552)(), (ct.c_uint8 * 552)()
                assert current.g135_compute(slot, ct.byref(value), new_out) == 0
                assert previous.g135_compute(slot, ct.byref(value), old_out) == 0
                assert bytes(new_out) == bytes(old_out), (unit, slot, item['label'], level)
                outputs[level] = bytes(new_out)
                digest.update(bytes(new_out))
                points += 1
                comparisons += 1
            for a, b in zip(item['levels'], item['levels'][1:]):
                adjacent_equal += outputs[a] == outputs[b]
    # Repeat in another order, so no call may rely on scratch left by its
    # immediately preceding calculation.
    random.Random(138 + unit).shuffle(cases)
    for slot, values in cases:
        value = K.Levels((ct.c_int16 * 10)(*values))
        new_out, old_out = (ct.c_uint8 * 552)(), (ct.c_uint8 * 552)()
        assert current.g135_compute(slot, ct.byref(value), new_out) == 0
        assert previous.g135_compute(slot, ct.byref(value), old_out) == 0
        assert bytes(new_out) == bytes(old_out), (unit, slot, values)
        comparisons += 1
assert points == 3430 and adjacent_equal == 0
result = dict(status='PASS_HOST_C', selectable_points=points,
              previous_engine_comparisons=comparisons, bytes_per_comparison=552,
              equal_adjacent_outputs=adjacent_equal, output_digest=digest.hexdigest(),
              dat_sha256=hashlib.sha256(new_dat).hexdigest(),
              previous_dat_sha256=hashlib.sha256(old_dat).hexdigest(),
              scope='Other controls default; this is not a Cartesian-product check')
(OUT / 'evidence/borrow-math.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
