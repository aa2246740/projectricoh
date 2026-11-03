"""Execute final relocated storage dispatcher against legal read-only state."""
from pathlib import Path
import json
import struct
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
import run_v35_g117 as v

v.bind()
h, product, watch = v.boot('50mm')
opened, image, error = v.fr.publish(h, product, watch)
assert not error and opened['ok'] and image
root = v.ROOT_ADDR
session = h.u(root + 56)
assert h.u(session + 340) == 0xe7fff
rows = []


def storage(op, args):
    q, reply = v.pe.SCRATCH + 0x300, v.pe.SCRATCH + 0x380
    h.b.write(q, struct.pack('>HHI14I', 1, 64, 0, *args))
    h.b.write(reply, bytes(32))
    h.put(root + 6, 1, 1)
    try:
        result = product.call(product.symbol_pc('rv_call'), (1, op, q, reply), steps=2000000)
    finally:
        h.put(root + 6, 0, 1)
    assert result['ok'], result
    parsed = struct.unpack('>HHi i IIIII', h.b.read(reply, 32))
    assert result['signed'] == parsed[2]
    row = dict(operation=op, status=result['signed'], token=parsed[5], capabilities=parsed[7])
    rows.append(row)
    return row


epoch = h.u(root + 52)
a = [0] * 14
assert storage(1, a)['capabilities'] == 3
for op in (3, 7, 8):
    a = [0] * 14
    a[0], a[2], a[3], a[5] = epoch, 2, 1, 4
    if op == 3:
        a[8] = 240
    if op == 7:
        a[9] = 2
    assert storage(op, a)['status'] == -12
a = [0] * 14
a[0], a[2], a[5], a[9], a[10] = epoch, 1, 1, 5, 2
assert storage(9, a)['status'] == -12
a = [0] * 14
a[0], a[2], a[5] = epoch, 1, 1
opened_read = storage(2, a)
assert opened_read['status'] == 0 and opened_read['token']
assert h.u(session + 292) == 0
a = [0] * 14
a[0], a[1], a[6], a[7] = epoch, opened_read['token'], image, 16
# RvPrivateContext is not needed here: the file-mode rejection happens before
# buffer validation. A write request cannot use the legitimate read-only token.
assert storage(5, a)['status'] == -10
a[6] = a[7] = 0
assert storage(6, a)['status'] == 0
reinit = product.engine(0, [])
assert reinit['ok'] and reinit['reply_status'] == 0
mutations = [r for r in product.native_log if r['op'] == 'absent']
write_opens = [r for r in product.native_log if r['op'] == 'open' and r['flags']]
assert not mutations and not write_opens and not product.files.live
(OUT / 'machine-gates.json').write_text(json.dumps(dict(status='PASS', session_capabilities=hex(h.u(session + 340)),
    cases=rows, repeated_init=reinit, mutations=mutations, write_opens=write_opens,
    native_log=product.native_log, note='Real final M32R dispatcher; file/SD/task boundaries are stubs.'), indent=2) + '\n')
print('PASS final-machine storage query=3 create/rename/delete/mark=CAPABILITY readonly-token-write=RANGE close=OK')
print('PASS repeated ig_init; all native mutations=0 write_open=0 live_handles=0')
