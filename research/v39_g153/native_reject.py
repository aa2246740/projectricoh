"""Run actual init rejection through the native constructor; count writes."""
from pathlib import Path
import argparse
import json
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H
from dat_format import sha

CASES=('r3-padding','r3-hole','r3-point-bound','r3-length-formula','r3-version-r2',
       'fx-area-crc','fx-header-crc','fx-index','fx-length-formula')

def check(name,unit):
    started=time.time_ns();t=time.monotonic();dat=HERE/'local/variants'/(name+'.DAT')
    result=dict(case=name,unit=unit,variant_sha256=sha(dat.read_bytes()),
                final_dat_sha256=sha(H.DAT.read_bytes()),started_ns=started)
    try:
        cam=Camera(unit,dat=dat);rows=cam.unit_rows();settings=cam.s_bytes(0,4096);writes=cam.writes();stores=[]
        cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e:stores.append(dict(address=hex(e.address),data=e.data.hex(),origin=e.origin)) if e.origin=='cpu' else None)
        cam.h.parent();entered=cam.m.fr.native(cam.h,0x20287080,steps=30000000)
        assert entered['ok'],entered
        assert cam.h.u(0x2022f5ac,1)==7,'init rejected but list is not stock seven rows'
        assert cam.unit_rows()==rows and cam.writes()==writes and not stores
        assert cam.s_bytes(0,4096)==settings
        result.update(status='PASS',rows=7,unit_W=cam.writes()-writes,S_stores=len(stores),
                      settings_unchanged=True,unit_rows_T_unchanged=True,root=cam.m.fr.root_fields(cam.h))
    except Exception:
        result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(seconds=time.monotonic()-t,ended_ns=time.time_ns())
        (HERE/'evidence'/f'reject-{name}-{unit}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES);p.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    args=p.parse_args()
    for name in (args.case,) if args.case else CASES:check(name,args.unit)

if __name__=='__main__':main()
