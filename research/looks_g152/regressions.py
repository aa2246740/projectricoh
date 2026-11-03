"""Read-only reuse of selected g150 cases against the g152 layout and bytes."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H
from dat_format import expand,sha
from math_reference import compute
from apply_checks import ui_audit

H.Camera=Camera
sys.modules['g139_host']=H
os.environ['G150_TEST_PACKAGE']='firmware/package_v38_g152_test'
os.environ['G150_RELEASE_PACKAGE']='firmware/package_v38_g152'
os.environ['G139_ENGINE']='firmware/engine_v60_g152'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

G=load('g139_check',HERE/'legacy/g139_check.py')
G.TEST_DAT=H.DAT
def host_compute(unit,slot,levels):
    raw=H.DAT.read_bytes();status,entry=compute(raw,H.UNITS[unit],expand(raw,H.UNITS[unit],slot),levels)
    assert status==0;return entry
G.host_compute=host_compute
I=load('g152_reused_independent',H.ROOT/'research/g150/independent_checks.py')
I.HERE=HERE
sys.modules['independent_checks']=I
FIXED=load('g152_reused_fixed',H.ROOT/'research/g150/g150_checks.py')
sys.modules['g150_checks']=FIXED
REVIEW=load('g152_reused_review',HERE/'legacy/review_checks.py')

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    p.add_argument('cases',nargs='+');args=p.parse_args();results=[]
    overall=time.monotonic();started=time.time_ns();created=[]
    original_camera=H.Camera
    def camera(*a,**kw):
        result=original_camera(*a,**kw);created.append(result);return result
    H.Camera=camera
    for case in args.cases:
        created.clear()
        tick=time.monotonic();entry=dict(case=case,unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns())
        try:
            if case in G.CASES:entry['details']=G.CASES[case](args.unit)
            elif case in FIXED.CASES:
                cam,details=FIXED.CASES[case](args.unit);details['native_UI_audit']=ui_audit(cam);entry['details']=details
            elif case in REVIEW.CASES:
                cam,details=REVIEW.CASES[case](args.unit);details['native_UI_audit']=ui_audit(cam);entry['details']=details
            else:
                cam,details=I.CASES[case](args.unit);details['native_UI_audit']=ui_audit(cam);entry['details']=details
            entry['status']='PASS'
        except Exception:entry.update(status='FAIL',error=traceback.format_exc())
        identities=[dict(path=str(p),sha256=sha(p.read_bytes())) for p in dict.fromkeys(c.dat_path for c in created)]
        entry.update(seconds=time.monotonic()-tick,ended_ns=time.time_ns(),dat_identities=identities,
                     dat_sha256=identities[-1]['sha256'] if identities else None)
        if case in ('dat-release-test','dat-test-release'):
            release=H.ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT'
            test=H.ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT'
            source,target=(release,test) if case=='dat-release-test' else (test,release)
            entry['record_input_DATs']=[dict(role=role,path=str(path),sha256=sha(path.read_bytes()))
                                       for role,path in (('record-source',source),('executed-target',target))]
        (HERE/'evidence'/f'reg-{args.unit}-{case}.json').write_text(json.dumps(entry,indent=2)+'\n')
        print(json.dumps({k:v for k,v in entry.items() if k!='details'}),flush=True);results.append(entry)
    summary=dict(status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',unit=args.unit,
                 cases=len(results),started_ns=started,ended_ns=time.time_ns(),seconds=time.monotonic()-overall,
                 dat_sha256=sha(H.DAT.read_bytes()),source='g150 cases unchanged; Camera layout/14-byte reads and the integer reference builder rebound to g152.')
    (HERE/'evidence'/f'regressions-{args.unit}.json').write_text(json.dumps(summary,indent=2)+'\n')
    if summary['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
