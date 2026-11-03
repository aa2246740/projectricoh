"""Native field sequences with device responses supplied at existing edges."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, ROOT, save, sha
from extra_once import record as record_extra
record_extra()
from key_probe import configure, ux, m, fr, pe, v
import native_sequence as sequence

def state(h, p):
    result = ux.snap(h, p)
    layout = json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    base = p.symbol_pc('n')
    result['adapter'] = {k:h.u(base+layout[k], 1) for k in ('failed','watch_view','view_lost','comm_failed')}
    if int.from_bytes(p.dat[28:32], 'big') == 122:
        result['adapter']['reason'] = h.b.read(base+layout['failed_text'],15).split(b'\0')[0].decode('ascii')
    result['epochs'] = list(__import__('struct').unpack('>12I', h.b.read(pe.ROOT_ADDR+8,48)))
    result['native_state']=h.u(0x205d9c00)
    result['adj_slot']=h.u(h.settings+0x39f,1)
    result['adj_items']=list(h.b.read(0x205d9bcc,4))
    return result

def monitor(h, p):
    layout = json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    address = p.symbol_pc('n') + layout['failed']
    records = []
    def changed(event):
        records.append(dict(address=hex(event.address), pc=hex(event.pc) if event.pc else None,
                            value=event.data.hex(), origin=event.origin))
    h.b.add_write_trace(address, address+1, changed)
    return records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('unit', choices=('50mm','28mm','mount'))
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--keys-only', action='store_true')
    parser.add_argument('--only',nargs='+')
    args = parser.parse_args()
    dat, elf = configure(args.baseline)
    v.python_backend.CACHE = OUT/'decode'/('field-'+args.unit+('-baseline' if args.baseline else '-122'))
    h, p, w = m.boot(args.unit)
    device=sequence.device_edges(h,p)
    input_start=sequence.prepare_input(h)
    h.parent()
    m.published(h,p,w)
    h.select_item_8()
    native_entry=sequence.open_image_from_adj(h,p,fr)
    native_entry['input_start']=input_start
    template = state(h,p)
    assert h.u(0x205d9c00)==56 and template['cursor']==template['list']['cursor']==4
    names = ['fn2_right_left','ok','disp','timer','plus','minus','adj','shutter_half','shutter_full',
             'lever_left','lever_right','dial_up','dial_down','panel_keys']
    if not args.keys_only:
        names += ['prewrite_busy','partial_busy','row_reset','ready_busy',
                  'capture_exit','capture_open','capture_after_fn2']
    if args.only:
        assert all(name in names for name in args.only)
        names=args.only
    records = []
    for name in names:
        sys.stdout.flush()
        pid = os.fork()
        if pid == 0:
            record = dict(unit=args.unit, case=name, dat_sha256=sha(dat.read_bytes()), before=template,native_entry=native_entry)
            writes = monitor(h,p)
            try:
                if name == 'fn2_right_left':
                    record['right'] = sequence.key(h,fr,0x12)
                    record['middle'] = state(h,p)
                    record['left'] = sequence.key(h,fr,0x11)
                elif name in ('ok','disp','timer','plus','minus','adj','shutter_half','shutter_full',
                              'lever_left','lever_right','dial_up','dial_down'):
                    raw = dict(ok=0x18, disp=0x15, timer=0x16, plus=0xf, minus=0x10, adj=0x17,
                        shutter_half=0xd,shutter_full=0xe,lever_left=0x1a,lever_right=0x1b,dial_up=0x21,dial_down=0x22)[name]
                    record['key'] = sequence.key(h,fr,raw)
                    if name=='disp':assert state(h,p)['rows']==11
                elif name=='panel_keys':
                    record['open']=sequence.key(h,fr,0x15)
                    assert state(h,p)['rows']==11
                    layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
                    record['steps']=[]
                    for parameter in range(4):
                        step=dict(parameter=parameter,down=sequence.key(h,fr,0x10))
                        if parameter==0:ux.matches(h,p,4,contrast=1)
                        step['next']=sequence.key(h,fr,0x15)
                        record['steps'].append(step)
                    record['exit']=sequence.key(h,fr,0x17)
                    assert state(h,p)['native_overlay']==0
                elif name in ('prewrite_busy','partial_busy'):
                    count = [0]
                    original = p.rpc.call
                    def busy(cmd,value):
                        count[0] += 1
                        if (name=='prewrite_busy' and count[0]<=3) or (name=='partial_busy' and 16<=count[0]<=19):
                            if count[0]==16:
                                result=original(cmd,value)
                                p.rpc.log[-1].update(device_result=result,result=-1,simulated=True)
                            else:
                                p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
                            return -1
                        return original(cmd,value)
                    p.rpc.call = busy
                    record['move'] = fr.move_key(h,0x20)
                    assert count[0]>0, 'The communication boundary must be reached.'
                    record['middle'] = state(h,p)
                    p.rpc.call = original
                    m.reopen(h,p,w)
                    record['reopened'] = state(h,p)
                    if not args.baseline:
                        assert record['reopened']['adapter']['failed'] == 0
                        assert record['reopened']['rows'] == 8
                elif name == 'row_reset':
                    ux.need(fr.move_key(h,0x20))
                    ux.matches(h,p,5)
                    ux.need(fr.press(h,0x2b))
                    record['selected'] = state(h,p)
                    p.rpc.overlay.clear();p.rpc.t=2
                    m.reopen(h,p,w)
                    record['restored'] = ux.matches(h,p,5)
                elif name == 'ready_busy':
                    p.ready=0;ux.need(fr.native(h,0x200935b4,(0,)))
                    h.parent();opened,_,error=fr.publish(h,p,w);ux.need(opened)
                    record['busy']=state(h,p)
                    assert error is None,error
                    assert record['busy']['root']['state']==3 and record['busy']['adapter']['failed']==0
                    p.ready=1;ux.need(fr.native(h,0x200935b4,(1,)))
                    m.reopen(h,p,w)
                    assert state(h,p)['rows']==8
                elif name in ('capture_exit','capture_open','capture_after_fn2'):
                    ux.need(fr.move_key(h,0x20));ux.matches(h,p,5)
                    record['selected']=state(h,p)
                    if name=='capture_after_fn2':
                        record['right']=sequence.key(h,fr,0x12)
                        record['left']=sequence.key(h,fr,0x11)
                    if name=='capture_exit':record['adj_exit']=sequence.key(h,fr,0x17)
                    record['half']=sequence.key(h,fr,0xd)
                    assert record['half']['logical']==0x29,record['half']
                    record['after_half']=state(h,p)
                    record['full']=sequence.key(h,fr,0xe)
                    assert record['full']['logical']==0x2a,record['full']
                    record['after_full']=state(h,p)
                    record['release_full']=sequence.key(h,fr,0xe,phase=0)
                    record['release_half']=sequence.key(h,fr,0xd,phase=0)
                    m.reopen(h,p,w)
                    record['restored']=ux.matches(h,p,5)
                record['after'] = state(h,p)
                record['status']='PASS'
                if name.startswith('capture_'):
                    record['status']='INCOMPLETE_CAPTURE_COMPLETION'
                    record['scope']='Raw keys, native UI states and reopen were executed. Unit completion and photo review were not supplied.'
            except BaseException:
                record['status']='FAIL';record['error']=traceback.format_exc()
                if name=='capture_exit' and 'unmapped memory 0xf0218814/4' in record['error']:
                    record['status']='INCOMPLETE_DEVICE_REGISTER'
                    record['scope']='The full-shutter prefix reached the unmodeled device register 0xf0218814 at native PC 0x203ce0ec.'
            finally:
                record['failed_writes']=writes
                record['file_mutations']=m.no_writes(p)
                record['rpc_log']=p.rpc.log
                record['device_calls']=device
                tag = 'baseline' if args.baseline else '122'
                save('field/'+tag+'-'+args.unit+'-'+name+'.json',record)
                print(record['status'],tag,args.unit,name,record.get('error','')[-600:],flush=True)
            os._exit(0 if record['status']=='PASS' else 1)
        _, status = os.waitpid(pid,0)
        records.append(dict(case=name,exit_status=status))
    save('field/'+('baseline' if args.baseline else '122')+'-'+args.unit+'.json',
         dict(status='PASS' if all(r['exit_status']==0 for r in records) else 'FAIL',cases=records,dat_sha256=sha(dat.read_bytes())))

if __name__ == '__main__':
    main()
