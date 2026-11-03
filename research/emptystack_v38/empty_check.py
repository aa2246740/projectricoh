from pathlib import Path
import inspect
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, LOCAL, setup, save, sha
from accept import module

R = 0x20054700

def main():
    setup()
    unit = sys.argv[1]
    old = module()
    m, h, p, w = old.boot(unit)
    identity = {'dat_sha256': sha(old.DAT), 'body_sha256': sha(old.BODY), 'unit': unit}
    h.parent()
    opened = m.fr.native(h, 0x20287080, (), 80000000)
    assert opened.get('ok'), opened
    assert old.snapshot(h)['rows'] == 8
    save(LOCAL / ('empty-api-' + unit + '.json'), dict(identity, opened=opened,
        native_signature=str(inspect.signature(m.fr.native)), call_signature=str(inspect.signature(p.call)),
        link_type=type(p.link).__name__, link_keys=list(p.link) if isinstance(p.link, dict) else [],
        resident_symbols=[k for k in h.symbols if k.startswith('rv_') or k == 'owned']))
    print(json.dumps({'phase': 'opened', 'unit': unit, 'state': old.snapshot(h)}), flush=True)
    resident = m.v.Elf(old.RESIDENT)
    symbols = resident.symbols
    def address(name):
        value = symbols[name]
        return value['value'] if isinstance(value, dict) else value
    pending = {'value': None}
    captured = []
    def entry(backend):
        if backend.get_reg('r1') == 1 and pending['value'] is not None:
            values = pending['value']
            pending['value'] = None
            for at, width, value in values:
                backend.write(at, int(value).to_bytes(width, 'big'))
            snap = old.snapshot(h)
            snap.update(empty_tag=h.u(0x205a279c,1), empty_state=hex(h.u(0x205a27a0)))
            captured.append(snap)
        return False
    h.b.add_breakpoint(address('rv_hook_observe'), entry)
    def prepare(**change):
        p.call(address('rv_ui_abort'), (R,))
        values = dict(part=1, count=0, tag=255, state=0x205a279c,
                      names=0x2022d610, rows=7, kind=5, activity=8, native=0x38)
        values.update(change)
        locations = {'part': (0x205a280f,1), 'count': (0x205a27d4,1),
                     'tag': (0x205a279c,1), 'state': (0x205a27a0,4),
                     'names': (0x2022f5a8,4), 'rows': (0x2022f5ac,1),
                     'kind': (0x2022f71c,1), 'activity': (0x205d9bf8,4),
                     'native': (0x205d9c00,4)}
        pending['value'] = [(0x205a27d8,4,0x205a279c)] + [(locations[k][0], locations[k][1], v) for k,v in values.items()]
    prepare()
    before = h.b.visits.get(0x202870a4,0)
    result = m.fr.native(h, 0x20287080, (), 80000000)
    after = old.snapshot(h)
    evidence = dict(identity, entry=captured[-1], result=result, after=after,
                    getter_delta=h.b.visits.get(0x202870a4,0)-before)
    save(LOCAL / ('empty-' + unit + '.json'), evidence)
    print(json.dumps(evidence), flush=True)
    assert after['rows'] == 8 and evidence['getter_delta'] == 0
    assert evidence['entry']['count'] == 0 and evidence['entry']['empty_tag'] == 255
    def call_bool(pc, arguments):
        result = p.call(pc, arguments)
        assert result.get('ok'), result
        return result['r0']
    evidence['resident_live'] = {str(hook): call_bool(address('owned'), (R,hook)) for hook in (1,2,5,6,7,8)}
    assert all(value == 1 for value in evidence['resident_live'].values())
    prior = h.u(0x205a27d4,1)
    h.put(0x205a27d4,0,1)
    evidence['resident_empty'] = {str(hook): call_bool(address('owned'), (R,hook)) for hook in (1,2,5,6,7,8)}
    assert evidence['resident_empty'] == {'1':1,'2':1,'5':0,'6':0,'7':0,'8':0}
    native_list = p.symbol_pc('n') + 2988
    saved_inflight = h.u(R+6,1)
    h.put(R+6,1,1)
    evidence['dat_empty'] = {str(mode): call_bool(p.symbol_pc('rv_view_owned'), (R,native_list,mode)) for mode in (0,1)}
    h.put(R+6,saved_inflight,1)
    h.put(0x205a27d4,prior,1)
    assert evidence['dat_empty'] == {'0':0,'1':1}
    evidence['negative'] = []
    cases = [('part0', {'part':0}), ('part4', {'part':4}),
             ('activity', {'activity':7}), ('native_state', {'native':0x37}),
             ('names', {'names':0x2022d614}), ('rows', {'rows':6})]
    for name, change in cases:
        prepare(**change)
        before = h.b.visits.get(0x202870a4,0)
        result = m.fr.native(h,0x20287080,(),80000000)
        snap = old.snapshot(h)
        record = {'name':name,'entry':captured[-1],'after':snap,'result':result,
                  'getter_delta':h.b.visits.get(0x202870a4,0)-before}
        evidence['negative'].append(record)
        save(LOCAL / ('empty-' + unit + '.json'), evidence)
        assert result.get('ok') and snap['rows'] != 8 and record['getter_delta'] == 1, record
        print(json.dumps({'phase':'negative','unit':unit,'name':name,'status':'PASS'}),flush=True)
    prepare()
    result = m.fr.native(h,0x20287080,(),80000000)
    assert result.get('ok') and old.snapshot(h)['rows'] == 8
    evidence['move'] = m.fr.move_key(h,32)
    assert evidence['move'].get('ok') and old.snapshot(h)['rows'] == 8
    evidence['disp'] = m.fr.native(h,0x202be220,(),80000000)
    assert evidence['disp'].get('ok') and old.snapshot(h)['rows'] == 8
    evidence['hook_visits'] = {str(hook):h.b.visits.get(address('rv_hook_'+str(hook).zfill(2)),0) for hook in (5,6,8)}
    assert all(value>0 for value in evidence['hook_visits'].values()), evidence['hook_visits']
    save(LOCAL / ('empty-' + unit + '.json'), evidence)
    evidence['writes'] = m.no_writes(p)
    evidence['status'] = 'PASS'
    save(LOCAL / ('empty-' + unit + '.json'), evidence)
    print(json.dumps({'phase':'complete','unit':unit,'status':'PASS'}),flush=True)

if __name__ == '__main__':
    main()
