"""Observe the real DAT service rejecting one nonzero detail word in model RAM."""
from pathlib import Path
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import save
from product_probe import setup


def main():
    m, v, fr, pe = setup('service-gate')
    h, p, watch = m.boot('50mm')
    armed, records = [], []
    installed = {'done': False}

    def rv_call(b):
        if records or armed or b.get_reg('r0') != 10 or b.get_reg('r1') != 1:
            return False
        q, reply = b.get_reg('r2'), b.get_reg('r3')
        u = h.u(q+48)
        details = h.u(u+32)
        assert h.u(details) == 0
        h.put(details, 1)
        target = b.get_reg('r14')
        record = dict(service=10, operation=1, input_detail_word=1,
                      source_is_model_engine_BSS=True, reply=reply)
        armed.append(record)

        def returned(bb):
            if armed:
                value = bb.get_reg('r0')
                signed = value-(1 << 32) if value & (1 << 31) else value
                record.update(result=signed, reply_status=h.u(reply+4), return_pc=hex(target))
                records.append(record)
                h.put(details, 0)
                armed.clear()
            return False

        h.b.add_breakpoint(target, returned)
        return False

    def before_engine(b):
        block = h.u(pe.ROOT_ADDR+56)
        if block and not installed['done']:
            image = block+1104
            h.b.add_breakpoint(image+p.elf.symbols['rv_call'], rv_call)
            installed['done'] = True
        return False

    h.b.add_breakpoint(h.symbols['rv_engine'], before_engine)
    opened, image, error = fr.publish(h, p, watch)
    assert len(records) == 1 and records[0]['result'] == -4, records
    assert records[0]['reply_status'] == 0xfffffffc
    save('service-gate.json', dict(status='PASS_REJECTION', records=records,
        opened=opened, error=error, dat_sha256=pe.STAGED_SHA,
        restored_source_detail_word=0, expected='RV_UNSUPPORTED=-4',
        evidence_scope='Controlled nonzero source word during a real menu RV_UI_LIST call. '
        'This is a rejected format case, not successful hint publication.'))
    print('PASS native RV_UI_LIST returns RV_UNSUPPORTED for nonzero details')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        save('service-gate-failure.json', dict(status='FAIL', traceback=traceback.format_exc()))
        raise
