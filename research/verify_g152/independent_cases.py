"""Additional observations of final M32R paths and complete unit state."""
from pathlib import Path
from fractions import Fraction
import argparse
import json
import time
import traceback

OUT = Path(__file__).resolve().parent


def snapshot_race(unit, kind):
    from native_support import Camera, H, snapshot, expected, exit_menu
    from dat_format import expand, sha
    from apply_checks import ui_audit
    from unverified_checks import P
    cam = Camera(unit)
    raw = H.DAT_BYTES[cam.dat_path]
    source = expand(raw, H.UNITS[unit], 2)
    changed = bytearray(expand(raw, H.UNITS[unit], 8))
    if kind == 'T':
        changed = bytearray(source)
        changed[445:447] = bytes(2)
    changed = bytes(changed)
    P.set_unit_rows(cam, source)
    cam.put_s(0x36e, b'\x04')
    cam.open_menu()
    before = snapshot(cam)
    assert cam.engine_bytes(H.LAYOUT['g.baseline'], 1) == b'\0'
    cam.h.b.core.psw |= 0x40
    reads = []
    stores = []
    original = cam.p.rpc.call
    def transport(cmd, value):
        is_t = cmd == 21 and cam.p.rpc.page == 0x12c0
        result = original(cmd, value)
        if is_t:
            reads.append(result)
            if len(reads) == 2:
                assert cam.writes() == before['W'] == 0
                P.set_unit_rows(cam, changed)
        return result
    cam.p.rpc.call = transport
    cam.h.b.add_write_trace(cam.s, cam.s+4096,
                           lambda e: stores.append(e.address-cam.s) if e.origin == 'cpu' else None)
    cam.press('DOWN')
    frame = cam.check_frame()
    assert len(reads) >= 3
    assert frame['failed'] and frame['screen'] == 6
    assert cam.engine_bytes(H.LAYOUT['g.live_verified'], 1) == b'\0'
    assert cam.engine_bytes(H.LAYOUT['g.snapshot_fault'], 1) == b'\1'
    assert cam.engine_bytes(H.LAYOUT['g.uncertain'], 1) == b'\1'
    assert cam.writes() == 0 and not stores and cam.s_bytes(0,4096) == before['S']
    assert cam.unit_rows() == expected(cam, changed)
    exits = []
    for how in ('ok', 'half', 'menu'):
        exit_menu(cam, how)
        cam.open_menu()
        again = cam.check_frame()
        assert again['failed'] and cam.engine_bytes(H.LAYOUT['g.uncertain'], 1) == b'\1'
        assert cam.s_bytes(0,4096) == before['S'] and cam.writes() == 0
        assert cam.unit_rows() == expected(cam, changed)
        exits.append(dict(kind=how, frame=again))
    return dict(unit=unit, kind=kind, initial_entry_sha256=sha(source), changed_entry_sha256=sha(changed),
                changed_at='After the first complete read of rows and its final T reply, before the second read.',
                T_replies=reads, unit_W=0, S_stores=stores, frame=frame, exits=exits,
                native_UI_audit=ui_audit(cam), dat_sha256=sha(raw))


def after_refusal(unit,next_slot=8):
    from native_support import Camera,H,snapshot,expected,exit_menu
    from dat_format import expand,sha
    from unverified_checks import P,C
    from lock_checks import serial,callback_return
    from apply_checks import ui_audit
    cam=Camera(unit)
    raw=H.DAT_BYTES[cam.dat_path]
    first=expand(raw,H.UNITS[unit],2)
    second=expand(raw,H.UNITS[unit],next_slot)
    target=expand(raw,H.UNITS[unit],5)
    P.set_unit_rows(cam,first)
    cam.put_s(0x36e,b'\x04')
    cam.open_menu()
    C.model_lock(cam,0)
    cam.press('DOWN')
    assert cam.unit_rows()==expected(cam,first) and cam.writes()==0
    # verify copy: the next line asserted the stale snapshot flag (the defect state); removed for the fixed build
    assert cam.engine_bytes(H.LAYOUT['g.baseline'],1)==b'\0'
    exit_menu(cam,'ok')
    assert cam.h.u(0x2022f5ac,1)==7
    flags_after_exit={key:cam.engine_bytes(H.LAYOUT['g.'+key],1).hex() for key in
                      ('baseline','committed','live_verified','uncertain','snapshot_fault')}
    # A later unit state is an explicit model input at the closed menu.
    # The existing native contract permits row changes without an epoch
    # change; validate_live documents this reason for re-reading at entry.
    P.set_unit_rows(cam,second)
    C.model_lock(cam,-1)
    closed=snapshot(cam)
    cam.open_menu()
    assert cam.unit_rows()==expected(cam,second) and cam.writes()==0
    before=snapshot(cam)
    before_live=cam.engine_bytes(H.LAYOUT['g.live'],552)
    cam.h.b.core.psw|=0x40
    calls=[]
    taken=[]
    stores=[]
    def call(b):
        if b.core.r[0]==6 and b.core.r[1] in (2,5,6):
            if b.core.r[1]==2 and not taken:
                assert b.core.psw&0x40
                C.model_lock(cam,0)
                taken.append(True)
            row=dict(op=b.core.r[1])
            calls.append(row)
            def returned(current):
                v=current.core.r[0]
                row['returned']=v-2**32 if v>=2**31 else v
            callback_return(cam,b,returned)
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    cam.h.b.add_write_trace(cam.s,cam.s+4096,
                           lambda e:stores.append(e.address-cam.s) if e.origin=='cpu' else None)
    cam.press('DOWN')
    after=snapshot(cam)
    frame=cam.check_frame()
    matches={name:cam.unit_rows()==expected(cam,entry) for name,entry in
             (('first_snapshot_02',first),('actual_prior',second),('target_05',target),('stock_04',expand(raw,H.UNITS[unit],4)))}
    exit_menu(cam,'ok')
    cam.open_menu()
    reopened=snapshot(cam)
    result=dict(unit=unit,dat_sha256=sha(raw),before=serial(before),after=serial(after),
                after_reopen=serial(reopened),calls=calls,S_stores=stores,frame=frame,
                reopened_frame=cam.check_frame(),matches=matches,
                original_snapshot_sha256=sha(first),actual_prior_sha256=sha(second),
                actual_prior_slot=next_slot,flags_after_first_exit=flags_after_exit,
                cached_live_before_second_choice_sha256=sha(before_live),
                native_UI_audit=ui_audit(cam))
    result['contract_pass']=matches['actual_prior'] or matches['target_05'] or (matches['stock_04'] and frame['failed'])
    label='after-refusal-'+str(next_slot)+'-'+unit
    for name,state in (('before',before),('after',after),('reopened',reopened)):
        (OUT/'runtime/evidence'/(label+'-'+name+'.bin')).write_bytes(b''.join(state['rows'])+state['T'].to_bytes(2,'big'))
        (OUT/'runtime/evidence'/(label+'-'+name+'-S.bin')).write_bytes(state['S'])
    (OUT/'runtime/evidence'/(label+'-observation.json')).write_text(json.dumps(result,indent=2)+'\n')
    assert result['contract_pass'], 'The actual prior state changed after the first refused choice.'
    return result


def reject_all(unit,names=None):
    from native_support import Camera, H
    from dat_format import sha
    from native_reject import CASES
    from apply_checks import ui_audit
    records = []
    for name in (CASES if names is None else names):
        dat = OUT/'runtime/local/variants'/(name+'.DAT')
        cam = Camera(unit, dat=dat)
        rows, settings, writes = cam.unit_rows(), cam.s_bytes(0,4096), cam.writes()
        stores, roots, capabilities, capability_stores, watched_blocks = [], [], [], [], set()
        load_entered=[False]
        def load_begin(b):
            load_entered[0]=True
            assert not cam.h.u(H.R+212)&128
            return False
        cam.h.b.add_breakpoint(cam.h.symbols['rv_load'],load_begin)
        cam.h.b.add_write_trace(cam.s, cam.s+4096,
                               lambda e: stores.append(e.address-cam.s) if e.origin == 'cpu' else None)
        # RvRoot.flags at +212 publishes the accepted session. Observe the
        # complete write history, including a value later cleared on failure.
        def root_store(e):
            if e.origin == 'cpu':
                roots.append(dict(address=e.address, data=e.data.hex()))
                if load_entered[0]: assert not cam.h.u(H.R+212) & 128
        cam.h.b.add_write_trace(H.R+212, H.R+216, root_store)
        # Real loader invokes through rv_invoke(address, api, context, q, p).
        # At ig_init entry, r3 is its RvReply. Inspect the return value before
        # any retirement can clear the reply or session.
        # The image address is allocated during the native constructor. A
        # resident entry callback discovers ig_init after relocation.
        def invoke(b):
            block = cam.h.u(H.R+56)
            if 0x20000000 <= block < 0x21000000:
                if block not in watched_blocks:
                    watched_blocks.add(block)
                    def cap_store(e):
                        if e.origin=='cpu':
                            value=cam.h.u(block+340)
                            capability_stores.append(value)
                            assert value&0xf0000==0
                    cam.h.b.add_write_trace(block+340,block+344,cap_store)
                image = cam.h.u(block+312)
                if image and b.core.r[0] == image+cam.p.elf.symbols['ig_init']:
                    reply = cam.h.u(b.core.r[15])
                    ret = b.core.r[14]
                    active = [True]
                    def returned(current):
                        if active[0]:
                            active[0] = False
                            value = cam.h.u(reply+24)
                            capabilities.append(value)
                            assert value & 0xf0000 == 0
                        return False
                    cam.h.b.add_breakpoint(ret, returned)
            return False
        cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'], invoke)
        tick = time.monotonic()
        cam.h.parent()
        entered = cam.m.fr.native(cam.h, 0x20287080, steps=30000000)
        assert entered['ok'], entered
        assert cam.h.u(0x2022f5ac,1) == 7
        assert cam.unit_rows() == rows and cam.writes() == writes and not stores
        assert cam.s_bytes(0,4096) == settings
        assert not cam.h.u(H.R+212) & 128
        if name.startswith('r3-'): assert capabilities==[0], capabilities
        result = dict(case=name, variant_sha256=sha(dat.read_bytes()), rows=7, unit_W=0, S_stores=0,
                      published_flag_never_set=True, root_flag_writes=roots,
                      init_return_capabilities=capabilities,session_capability_stores=capability_stores,
                      native_UI_audit=ui_audit(cam),
                      seconds=time.monotonic()-tick)
        records.append(result)
        (OUT/'runtime/evidence'/('own-reject-'+name+'-'+unit+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        print('REJECT', name, round(result['seconds'],3), flush=True)
    return dict(unit=unit, cases=records, dat_sha256=sha(H.DAT.read_bytes()))


def isolated_area(unit):
    from native_support import H
    from dat_format import effect_area,u32,crc,seal,sections,strict_effects,sha
    from format_checks import variants,fix_effects
    raw=H.DAT.read_bytes()
    at,n=effect_area(raw)
    original=variants(raw)['fx-area-crc']
    old_header=u32(original,at+28)==crc(original[at:at+28])
    old_area=u32(original,at+24)==crc(original[at+32:at+n])
    assert not old_header and not old_area
    candidate=bytearray(raw)
    candidate[at+32+20]^=1
    candidate=seal(candidate)
    sections(candidate)
    assert u32(candidate,at+28)==crc(candidate[at:at+28])
    assert u32(candidate,at+24)!=crc(candidate[at+32:at+n])
    strict_effects(fix_effects(bytearray(candidate)))
    path=OUT/'runtime/local/variants/fx-area-isolated.DAT'
    path.write_bytes(candidate)
    result=dict(dat_sha256=sha(raw),variant_sha256=sha(candidate),
                original_fixture=dict(header_crc_matches=old_header,area_crc_matches=old_area),
                isolated_fixture=dict(header_crc_matches=True,area_crc_matches=False,
                                      envelope_CRCs_valid=True,fully_valid_after_only_CRC_repair=True))
    (OUT/'runtime/evidence/area-crc-isolation.json').write_text(json.dumps(result,indent=2)+'\n')
    native=reject_all(unit,('fx-area-isolated',))
    assert native['cases'][0]['init_return_capabilities']==[0]
    result['native']=native
    return result


def bw(unit):
    from native_support import Camera, H, expected
    from dat_format import expand_effect, expand, sha
    from apply_checks import ui_audit
    cam = Camera(unit)
    cam.open_menu()
    cam.open_looks()
    cam.select_effect(3)
    raw = H.DAT_BYTES[cam.dat_path]
    entry = expand_effect(raw,2)
    rows, t = cam.unit_rows()
    assert (rows,t) == expected(cam,entry)
    assert cam.engine_bytes(H.LAYOUT['g.live'],552) == entry
    colour = rows[2]
    assert len(colour) == 96 and colour == bytes(96)
    assert colour == expand(raw,H.UNITS[unit],3)[115:211]
    # Decode the stored signed-magnitude coefficient bytes directly. No
    # effect id, name, or prediction callback chooses a grey output here.
    signed = lambda v: -(v & 127) if v & 128 else v
    coeffs = [(signed(colour[4*i]),signed(colour[4*i+1])) for i in range(24)]
    count = 0
    for sector in range(24):
        left, right = coeffs[sector], coeffs[(sector+1)%24]
        for weight in range(257):
            a = Fraction((256-weight)*left[0]+weight*right[0], 8192)
            b = Fraction((256-weight)*left[1]+weight*right[1], 8192)
            for cb,cr in ((0,0),(127,-128),(-128,127),(4095,-4095)):
                out_cb, out_cr = cb*a+cr*b, cr*a-cb*b
                for y in (0,31,128,255):
                    rgb = (y+Fraction(1402,1000)*out_cr,
                           y-Fraction(344136,1000000)*out_cb-Fraction(714136,1000000)*out_cr,
                           y+Fraction(1772,1000)*out_cb)
                    assert rgb == (y,y,y)
                    count += 1
    return dict(unit=unit, dat_sha256=sha(raw), live_552_sha256=sha(entry), C080_hex=colour.hex(),
                decoded_coefficients=coeffs, exact_RGB_cases=count, native_UI_audit=ui_audit(cam),
                scope='Final encoded rows actually written by M32R; exact zero-chroma calculation, no photograph.')


def text12(unit):
    from native_support import Camera, H
    from dat_format import sha
    from apply_checks import ui_audit
    dat = OUT/'runtime/local/variants/name12.DAT'
    cam = Camera(unit,dat=dat)
    cam.open_menu()
    seen = []
    def call(b):
        if tuple(b.core.r[:2]) == (11,1):
            q = b.core.r[2]
            text = cam.h.u(q+48)
            source,n = cam.h.u(text+8),cam.h.u(text+12)
            data = bytes(cam.h.b.read(source,n+1))
            assert n <= 13 and data[-1] == 0
            seen.append(dict(length=n, data=data.hex()))
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    cam.open_looks()
    cam.select_effect(1)
    cam.press('DISP')
    frame = cam.check_frame()
    adapter = cam.adapter+H.UI+H.LAYOUT['ui.text']
    rendered = cam.adapter+H.UI+H.LAYOUT['ui.frame']
    arrays = {}
    for label,address in (('adapter',adapter),('frame',rendered)):
        rows = [bytes(cam.h.b.read(address+14*i,14)) for i in range(8)]
        assert all(b'\0' in row for row in rows)
        arrays[label] = [row.hex() for row in rows]
    assert any(x['length']==13 for x in seen)
    assert bytes(cam.h.b.read(adapter,14))[-1] == 0 and len(frame['labels'][0]) == 13
    return dict(unit=unit, fixture_sha256=sha(dat.read_bytes()), frame=frame, text_calls=seen,
                arrays=arrays, native_UI_audit=ui_audit(cam))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('case',choices=('snapshot-race','after-refusal','after-refusal-stock','reject','isolated-area','bw','text12','static'))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),default='mount')
    p.add_argument('--kind',choices=('T','rows'),default='rows')
    a=p.parse_args()
    record=dict(case=a.case,unit=a.unit,kind=a.kind,started_ns=time.time_ns())
    tick=time.monotonic()
    try:
        if a.case=='static':
            import static_checks
            static_checks.main()
        elif a.case=='snapshot-race': record['details']=snapshot_race(a.unit,a.kind)
        elif a.case=='after-refusal': record['details']=after_refusal(a.unit)
        elif a.case=='after-refusal-stock': record['details']=after_refusal(a.unit,4)
        elif a.case=='isolated-area': record['details']=isolated_area(a.unit)
        else: record['details']={'reject':reject_all,'bw':bw,'text12':text12}[a.case](a.unit)
        record['status']='PASS'
    except BaseException:
        record.update(status='FAIL',error=traceback.format_exc())
        raise
    finally:
        record.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (OUT/'runtime/evidence'/f'own-{a.case}-{a.unit}-{a.kind}.json').write_text(json.dumps(record,indent=2)+'\n')
        print('OWN_RESULT',json.dumps({k:v for k,v in record.items() if k!='details'}),flush=True)


if __name__=='__main__': main()
