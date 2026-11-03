"""Short native smoke test retained as a reproducible command."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    args=parser.parse_args()
    ux,m,fr,pe,v=setup(unit=args.unit,tag='probe')
    from runtime_guard import install
    install(v)
    h,p,w=m.boot(args.unit)
    m.published(h,p,w)
    offsets=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    adapter=p.symbol_pc('n')
    def state():
        return dict(screen=h.u(adapter+offsets['ui.screen'],1),logical=h.u(adapter+offsets['ui.cur'],1),
                    physical=h.u(0x2022f726,1),rows=h.u(0x2022f5ac,1),
                    text=[h.b.read(adapter+offsets['ui.text']+9*i,9).split(b'\0')[0].decode() for i in range(8)])
    report=dict(dat_sha256=sha(p.dat),initial=state(),events=[])
    print('OPEN',state(),flush=True)
    for action in ('down','disp','disp','disp','up','down','disp','ok'):
        result=fr.move_key(h,0x20 if action=='down' else 0x1f) if action in ('up','down') else fr.native(h,0x202be220) if action=='disp' else fr.press(h,0x23)
        report['events'].append(dict(action=action,result=result,state=state()))
        print(action,result,state(),flush=True)
        ux.need(result)
    report.update(rpc_log=p.rpc.log,native_UI=ui_audit(h),file_mutations=m.no_writes(p))
    save('local/probe-'+args.unit+'.json',report)

if __name__=='__main__':main()
