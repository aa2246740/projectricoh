"""Early focused verification of shared-CPU scheduling and Fn2 recovery."""
import argparse
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import native_ux as ux

def run(unit,r,fn2_only=False):
    m,fr=ux.m,ux.fr
    h,p,w=m.boot(unit);ins=ux.instrument(h,p)
    m.published(h,p,w);ux.arm_entries(h,p,ins)
    if not fn2_only:
        r['nested']=ux.nested_navigation(h,p,ins)
        print('PASS focused nested',unit,flush=True)
    ux.move_to(h,p,5,ins);ux.need(fr.native(h,0x202be220))
    panel=ux.snap(h,p);assert panel['rows']==11 and panel['cursor']==6,panel
    at=len(ins['events']);mark=w.mark();write_mark=len(h.writes)
    ux.need(fr.move_key(h,0x20))
    r['fn2_move']=dict(after=ux.snap(h,p),events=ins['events'][at:],hooks=w.since(mark),
                        writes=h.writes[write_mark:])
    ux.need(fr.press(h,0x2b))
    r['fn2_accept']=dict(after=ux.snap(h,p),events=ins['events'][at:],hooks=w.since(mark))
    layout=json.loads((HERE/'local/layout/layout.json').read_text())
    g=p.symbol_pc('g')
    entry,mapping=ux.m.unpack(p.dat,ux.m.INDEX[unit],5)
    row=mapping[44:56];address,n,off=ux.m.u32(row,0),ux.m.u16(row,4),ux.m.u16(row,6)
    actual_row=bytes((p.rpc.half(a&~1)>>(0 if a&1 else 8))&255 for a in range(address,address+n))
    r['fn2_observed']=dict(panel=panel,after=ux.snap(h,p),tweak=list(h.b.read(g+layout['tweak'],8)),
        actual_B5=actual_row.hex(),base_B5=entry[off:off+n].hex(),
        expected_by_level={str(i):ux.expected_entry(p,5,i)[0][off:off+n].hex() for i in (-2,-1,0,1,2)})
    actual=ux.matches(h,p,5,contrast=1);m.reopen(h,p,w)
    assert h.u(0x2022f726,1)==5
    ux.need(fr.move_key(h,0x20));ux.matches(h,p,6)
    ux.need(fr.move_key(h,0x1f));ux.matches(h,p,5,contrast=1)
    fail,original=ux.injected_rpc(p,16,after_write=True)
    step=ux.measure_move(h,p,0x20,ins);p.rpc.call=original
    assert fail['fired'] and step['after']['cursor']==5
    ux.matches(h,p,5,contrast=1)
    ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
    r['fn2']=dict(panel=panel,actual=actual,failure=fail,step=step,reopened=ux.snap(h,p))
    r['fn2']['half_exit']=ux.fn2_half_exit(h,p,w,ins)
    r['file_mutations']=m.no_writes(p);r['status']='PASS'
    print('PASS focused Fn2',unit,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('unit',choices=('50mm','28mm','mount'))
    p.add_argument('--fn2-only',action='store_true');a=p.parse_args()
    dat,elf=ux.configure(False,a.unit+'-edges')
    r=dict(unit=a.unit,dat_sha256=ux.m.sha(dat.read_bytes()),engine_elf_sha256=ux.m.sha(elf.read_bytes()))
    try:run(a.unit,r,a.fn2_only)
    except Exception:
        r['status']='FAIL';r['error']=traceback.format_exc();ux.save('edges-'+a.unit+'.json',r);raise
    ux.save('edges-'+a.unit+'.json',r)

if __name__=='__main__':main()
