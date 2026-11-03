"""Rerun existing native paths, with all output/cache destinations redirected."""
from pathlib import Path
import argparse
import json
import inspect
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, load, save, sha

ux=load(ROOT/'research/ux_preview_dot_r1/native_ux.py','native_ux')
m,fr,pe,v=ux.m,ux.fr,ux.pe,ux.v
ux.OUT=OUT/'native'
ux.save=lambda name,value:save('native/'+name,value)
m.OUT=OUT/'native/ah'
m.save=lambda name,value:save('native/ah/'+name,value)

def configure(unit):
    dat,elf=ux.configure(False,unit+'-independent')
    dat=ROOT/'firmware/package_v36_g118/SD_ROOT/GXRCE.DAT'
    m.DAT=dat;pe.STAGED=dat;pe.STAGED_SHA=sha(dat.read_bytes())
    v.python_backend.CACHE=OUT/'decode'/unit
    assert pe.STAGED_SHA=='e557c7266c05ea5b997bd369b505ea364c660e87aef07180c784207ffd0f3f2d'
    return dat,elf

def main():
    a=argparse.ArgumentParser();a.add_argument('group',choices=('matrix','exits','perf','persistent','ah'))
    a.add_argument('unit',choices=('50mm','28mm','mount'));args=a.parse_args()
    dat,elf=configure(args.unit)
    if args.group not in ('perf','persistent'):
        # Functional replay retains the existing, validated CRC-32 boundary.
        # No UI getter, event handler, transaction or apply path is substituted.
        for name in ('arm_entries','measure_move'):
            original=inspect.getsource(getattr(ux,name))
            routed=original.replace("h.b.breakpoints.pop(p.symbol_pc('gxr2_crc_add'),None)", 'pass # keep validated CRC acceleration for functional replay')
            exec(compile(routed, str(OUT/(name+'-functional-routing.py')), 'exec'), ux.__dict__)
            (OUT/(name+'-functional-routing.patch')).write_text(''.join(__import__('difflib').unified_diff(
                original.splitlines(True),routed.splitlines(True),fromfile='author/'+name,tofile='review/'+name)))
    r=dict(unit=args.unit,group=args.group,dat_sha256=sha(dat.read_bytes()),elf_sha256=sha(elf.read_bytes()),
           body_sha256=v.BODY_SHA,getter_fixed_return_stub_removed=True,native_ui_hand_seeded=False)
    r['crc_boundary']='real bit loop' if args.group in ('perf','persistent') else 'existing CRC-32 equivalent accelerator; boot loads run the real bit loop'
    started=time.monotonic()
    try:
        if args.group=='matrix':ux.matrix(args.unit,r)
        elif args.group=='exits':
            exits=load(ROOT/'research/ux_preview_dot_r1/native_exits.py','g118_native_exits')
            exits.run(args.unit,r)
        elif args.group=='perf':ux.perf(args.unit,r)
        elif args.group=='persistent':
            h,p,w=m.boot(args.unit);ins=ux.instrument(h,p);m.published(h,p,w);ux.arm_entries(h,p,ins)
            before=ux.snap(h,p);actual=p.rpc.call;calls=0
            def failed(cmd,value):
                nonlocal calls
                calls+=1
                if calls==16:
                    actual(cmd,value);p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,injected=True)
                    return -1
                if calls>16:
                    p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,injected=True))
                    return -1
                return actual(cmd,value)
            p.rpc.call=failed;r['move']=ux.measure_move(h,p,0x20,ins)
            r['before']=before;r['after']=ux.snap(h,p);r['rpc_log']=p.rpc.log
            r['matching_complete_slots']=[];r['mismatches']={}
            for slot in range(1,9):
                try:ux.matches(h,p,slot)
                except AssertionError as e:r['mismatches'][slot]=str(e)
                else:r['matching_complete_slots'].append(slot)
            assert not r['matching_complete_slots'] and r['after']['list']['uncertain']==1
            r['last_draw']=ins['dots'][-1] if ins['dots'] else None
            r['file_mutations']=m.no_writes(p)
            r['status']='REPRODUCED_MIXED_STATE'
            print('REPRODUCED persistent failure: no complete recipe among 01..08; uncertain=1',flush=True)
        else:
            # a,b,c,e and d/f have exact reusable assertions except generation.
            text=(ROOT/'firmware/engine_v39_ux/integration_native.py').read_text()
            import types
            ah=types.ModuleType('g118_ah_reference');ah.__file__=str(ROOT/'firmware/engine_v39_ux/integration_native.py')
            text=text.replace('==117', '==118').replace('== 117', '== 118')
            exec(compile(text,ah.__file__,'exec'),ah.__dict__)
            ah.DAT=dat;ah.OUT=OUT/'native/ah';ah.save=lambda name,value:save('native/ah/'+name,value)
            ah.FS_SETUP={};ah.ALL_PRODUCTS=[]
            pe.FileEdge=ah.Files;fr.Product=ah.Product
            ah.session(args.unit,r);ah.corruption(args.unit,r);ah.negative(args.unit,r);ah.stale_and_removed(args.unit,r)
            r['all_session_counters']=[ah.no_writes(p) for p in ah.ALL_PRODUCTS]
            r['status']='PASS'
    except Exception:
        r['status']='FAIL';r['error']=traceback.format_exc()
        raise
    finally:
        r['wall_seconds']=time.monotonic()-started
        save('native/'+args.group+'-'+args.unit+'.json',r)

if __name__=='__main__':main()
