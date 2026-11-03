"""Observe the owner-change path through reopening and OK without assuming its result."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import independent_checks as I
import g150_checks as F
import review_checks as C


def observe(unit):
    cam,stock,initial = F.p1_start(unit)
    cam.h.b.core.psw |= 0x40
    phase = ['forward']
    switched,events,services = [],[],[]
    calls = F.count_calls(cam); stores = F.s_stores(cam)
    generation = int.from_bytes(I.H.DAT_BYTES[cam.dat_path][28:32],'big')
    state_base = cam.symbol('g')
    state_fields = {'committed':4847,'uncertain':4848,'confirmed_valid':4856,'previewing':4857,
                    'settings_pending':4861,'s_busy':4894}
    if generation == 150:
        assert I.H.sha(I.H.ENGINE) == '8be7e95dde0df1351122551940754a8f007e6ed45bf9e8e2524ea7eee5fe7b21'
        state_fields['s_unwritten'] = 4896
    confirmed_stores, guard = [],[]
    def confirmed_store(e):
        if e.origin == 'cpu':
            confirmed_stores.append(dict(phase=phase[0],offset=e.address-state_base,data=e.data.hex(),pc=hex(e.pc)))
    for low,high in ((243,294),(314,334),(4856,4857)):
        cam.h.b.add_write_trace(state_base+low,state_base+high,confirmed_store)
    if generation == 150:
        def check_guard(b):
            assert b.core.r[8] == state_base
            guard.append(dict(phase=phase[0],s_unwritten=cam.h.u(state_base+4896,1),
                              pc='0x89f0'))
            return False
        cam.h.b.add_breakpoint(cam.p.image_base+0x89f0,check_guard)
    def call(b):
        key = tuple(b.core.r[:2])
        if key[0] == 6 and key[1] in (1,2,3,5,6):
            row = dict(phase=phase[0],op=key[1],lock=cam.lock(),mode=cam.s_bytes(0x36e,1).hex())
            services.append(row)
            def returned(current):
                n = current.core.r[0]
                row['returned'] = n-2**32 if n>=2**31 else n
            I.callback_return(cam,b,returned)
        if key == (4,3) and not switched:
            def returned(current):
                switched.append(I.switch_parent(cam))
                C.model_lock(cam,0)
            I.callback_return(cam,b,returned)
        return False
    def event(b):
        q = b.core.r[2]
        row = dict(phase=phase[0],event=cam.h.u(q+40),keep=cam.h.u(q+44),key=cam.h.u(q+60))
        events.append(row)
        def returned(current):
            row['returned'] = current.core.r[0]
        I.callback_return(cam,b,returned)
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    cam.h.b.add_breakpoint(cam.symbol('ig_event'),event)
    def snap():
        value = I.snapshot(cam)
        return dict(snapshot=I.serial_snapshot(value),mode=cam.s_bytes(0x36e,1).hex(),
                    WB=cam.s_bytes(0x6dd,2).hex(),record=cam.record().hex(),state=cam.state(),
                    engine={k:cam.h.u(state_base+o,1) for k,o in state_fields.items()})
    before = snap()
    cam.press('DOWN'); forward = snap()
    import g139_check as checks
    target = I.expected_rows(cam,checks.host_compute(unit,5,F.ZERO))
    assert switched and cam.unit_rows() == target and cam.s_bytes(0x36e,1) == b'\x04'
    phase[0] = 'reopen'
    cam.open_menu(); reopened = snap()
    phase[0] = 'OK'
    cam.press('OK'); after_OK = snap()
    if generation == 150:
        assert guard == [dict(phase='OK',s_unwritten=1,pc='0x89f0')], guard
        assert not [e for e in confirmed_stores if e['phase']=='OK'], confirmed_stores
    phase[0] = 'idle_reopen'
    C.model_lock(cam,-1)
    cam.open_menu(); after_idle = snap()
    return cam,dict(before=before,forward=forward,reopened=reopened,after_OK=after_OK,after_idle=after_idle,
                    events=events,services=services,calls=calls,stores=stores,
                    engine_state_offsets=state_fields,confirmed_stores=confirmed_stores,guard=guard,
                    observation_status='OBSERVED_OWNER_PATH',rows_equal_target=cam.unit_rows()==target)


if __name__ == '__main__':
    I.CASES.clear(); I.CASES['owner-path'] = observe; I.main()
