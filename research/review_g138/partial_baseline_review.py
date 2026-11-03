"""Observe 04 Default after a startup with one non-stock unit row."""
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ZERO = [100] + [0] * 9
reference = ROOT / 'research/g135_v37/local/target-cases-0.bin'
raw = reference.read_bytes()
entries = [raw[at+28:at+580] for at in range(0, len(raw), 580)
           if struct.unpack_from('>II', raw, at) == (0, 5)
           and list(struct.unpack_from('>10h', raw, at+8)) == ZERO]
assert entries and all(entry == entries[0] for entry in entries)
recipe = entries[0]
H.setup()
cam = H.Camera('50mm')
stock, stock_t = cam.unit_rows()
dat = H.DAT_BYTES[cam.dat_path]
directory = struct.unpack_from('>I', dat, 156)[0]
mapping_at = struct.unpack_from('>I', dat, directory+12)[0]
chosen = None
for index in range(9):
    address, count, offset = struct.unpack_from('>IHH', dat, mapping_at+32+12*index)
    wanted = recipe[offset:offset+count]
    if wanted != stock[index]:
        chosen = index
        for i, value in enumerate(wanted):
            at = address+i
            word = cam.p.rpc.half(at & ~1)
            assert word is not None
            cam.p.rpc.overlay[at & ~1] = ((word & 0xff00) | value) if at & 1 else ((word & 255) | value << 8)
        break
assert chosen is not None
mixed, control = cam.unit_rows()
assert sum(a != b for a, b in zip(mixed, stock)) == 1 and control == stock_t == 2
cam.put_s(0xfd4, H.record_bytes(dat, 5, 0, ZERO))
at = cam.writes()
cam.open_menu()
rejected = cam.check_frame()
assert not any(label.startswith('>') for label in rejected['labels'])
cam.press('DISP')
cam.goto(cam.ui('count')-1)
cam.press('DISP')
cam.press('DISP')
cam.goto(0)
cam.press('DISP')
accepted = cam.check_frame()
assert accepted['labels'][3] == '>4 Std' and accepted['failed'] == 0
assert cam.unit_rows() == (mixed, control) and cam.writes() == at
assert cam.record() == H.record_bytes(dat, 4, 0, ZERO)
cam.press('OK')
assert cam.unit_rows() == (mixed, control) and cam.writes() == at
result = dict(status='OBSERVED_M32R', observation='04_ACCEPTED_WITH_ONE_NONSTOCK_ROW',
              dat_sha256=H.sha(H.DAT), reference_sha256=H.sha(reference),
              changed_row=chosen, unit_writes=cam.writes()-at,
              rejected_state=rejected, accepted_state=accepted,
              stored_record_is04=True, persists_after_OK=True,
              S_mode=cam.s_bytes(0x36e, 1)[0], S_WB=list(cam.s_bytes(0x6dd, 2)),
              starting_state_source='one explicit model row input; native reachability not proven')
(OUT / 'evidence/partial-baseline.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
