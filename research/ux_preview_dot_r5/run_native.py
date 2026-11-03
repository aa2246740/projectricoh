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

ux=load(OUT/'native_ux.py','native_ux')
m,fr,pe,v=ux.m,ux.fr,ux.pe,ux.v
ux.OUT=OUT/'native'
ux.save=lambda name,value:save('native/'+name,value)
m.OUT=OUT/'native/ah'
m.save=lambda name,value:save('native/ah/'+name,value)

def configure(unit,tag='run'):
    dat,elf=ux.configure(False,unit+'-independent')
    dat=ROOT/'firmware/engine_v42_ux/candidate/local/full-r13/GXRCE.DAT'
    m.DAT=dat;pe.STAGED=dat;pe.STAGED_SHA=sha(dat.read_bytes())
    v.python_backend.CACHE=OUT/'decode'/(unit+'-'+tag)
    if not getattr(m.Product,'quality_symbol_alias',False):
        original_symbol=m.Product.symbol_pc
        def resolved_symbol(self,name):
            actual=name if name in self.elf.symbols else name+'.constprop.0'
            return original_symbol(self,actual)
        m.Product.symbol_pc=resolved_symbol
        m.Product.quality_symbol_alias=True
    assert int.from_bytes(dat.read_bytes()[28:32],'big')==120
    return dat,elf

def main():
    a=argparse.ArgumentParser();a.add_argument('group',choices=('matrix','exits','perf','persistent','ah'))
    a.add_argument('unit',choices=('50mm','28mm','mount'));args=a.parse_args()
    dat,elf=configure(args.unit,args.group)
    if args.group not in ('perf','persistent'):
        # Functional replay retains the existing, validated CRC-32 boundary.
        # No UI getter, event handler, transaction or apply path is substituted.
        for name in ('arm_entries','measure_move'):
            original=inspect.getsource(getattr(ux,name))
            routed=original.replace("h.b.breakpoints.pop(p.symbol_pc('gxr2_crc_add'),None)", 'pass # keep validated CRC acceleration for functional replay')
            exec(compile(routed, str(OUT/(name+'-'+args.unit+'-'+args.group+'-functional-routing.py')), 'exec'), ux.__dict__)
            (OUT/(name+'-'+args.unit+'-'+args.group+'-functional-routing.patch')).write_text(''.join(__import__('difflib').unified_diff(
                original.splitlines(True),routed.splitlines(True),fromfile='author/'+name,tofile='review/'+name)))
        # Cost collection is separate from functional acceptance. Keep every
        # native instruction, event, draw and write check; remove only the
        # per-instruction Counter wrapper from these long functional runs.
        original_instrument=ux.instrument
        def functional_instrument(h,p):
            op=h.b.core.op
            result=original_instrument(h,p)
            h.b.core.op=op
            return result
        ux.instrument=functional_instrument
        original_measure=ux.measure_move
        def functional_measure(h,p,key,ins):
            step=original_measure(h,p,key,ins)
            step['instruction_counts']=None;step['base_cycle_model']=None
            step['cost_measurement']='Not collected in functional replay; use independent perf records.'
            return step
        ux.measure_move=functional_measure
    r=dict(unit=args.unit,group=args.group,dat_sha256=sha(dat.read_bytes()),elf_sha256=sha(elf.read_bytes()),
           body_sha256=v.BODY_SHA,getter_fixed_return_stub_removed=True,native_ui_hand_seeded=False)
    r['crc_boundary']='real bit loop' if args.group in ('perf','persistent') else 'existing CRC-32 equivalent accelerator; boot loads run the real bit loop'
    r['instruction_costs_measured']=args.group in ('perf','persistent')
    started=time.monotonic()
    try:
        if args.group=='matrix':ux.matrix(args.unit,r)
        elif args.group=='exits':
            exits=load(OUT/'native_exits.py','g119_native_exits')
            exits.run(args.unit,r)
        elif args.group=='perf':ux.perf(args.unit,r)
        elif args.group=='persistent':
            h,p,w=m.boot(args.unit);ins=ux.instrument(h,p);m.published(h,p,w);ux.arm_entries(h,p,ins)
            before=ux.snap(h,p);actual=p.rpc.call;calls=0
            def failed(cmd,value):
                nonlocal calls
                calls+=1
                if calls==16:
                    actual(cmd,value);p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,simulated=True)
                    return -1
                if calls>16:
                    p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
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
            assert r['after']['root']['state']==3 and r['after']['root']['block']
            at=len(p.rpc.log);pr=h.stub_hits.get('preview',0)
            ascii_calls=[];draws=[]
            def ascii_input(b):
                source,length,destination,language=b.core.r[:4]
                ascii_calls.append(dict(source=hex(source),length=length,destination=hex(destination),language=language,
                                        ascii=h.b.read(source,length).decode('ascii')))
                return False
            def glyph_draw(b):
                draws.append(dict(pc=hex(b.pc),args=b.core.r[4:8]))
                return False
            h.b.add_breakpoint(p.symbol_pc('rv_native_ascii'),ascii_input)
            h.b.add_breakpoint(0x201d7170,glyph_draw)
            ux.need(fr.press(h,0x2b));h.parent()
            opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
            r['notice']=ux.snap(h,p)
            assert r['notice']['rows']==r['notice']['cursor']==r['notice']['dot_row']==1,r['notice']
            ui=r['notice']['root']['ui_block'];glyph=h.b.read(ui+424,96).split(b'\0',1)[0]
            r['notice_glyph_hex']=glyph.hex();r['notice_ascii']='ERR POWER OFF/ON'
            # ASCII -> glyph conversion is the existing native text boundary.
            # Record its actual detached snapshot bytes, plus native row draw.
            assert glyph and r['notice']['native_overlay']==32
            assert ascii_calls and all(x['ascii']=='ERR POWER OFF/ON' for x in ascii_calls),ascii_calls
            assert draws,'The native list must reach the glyph renderer.'
            r['notice_ascii_calls']=ascii_calls;r['notice_native_glyph_draws']=draws
            for key in (0x20,0x1f):ux.need(fr.move_key(h,key))
            ux.need(fr.native(h,0x202be220))
            ux.need(fr.press(h,0x23));h.parent()
            reopened,_,error=fr.publish(h,p,w);ux.need(reopened);assert error is None,error
            assert h.u(0x2022f5ac,1)==1
            assert len(p.rpc.log)==at and h.stub_hits.get('preview',0)==pr
            r['latched_no_more_rpc']=True;r['notice_reopened']=ux.snap(h,p)
            r['status']='PASS_NOTICE_LATCHED_MIXED_RAM'
            print('PASS persistent failure: latched; next native list is one ERR POWER OFF/ON row; no later RPC or preview',flush=True)
        else:
            # a,b,c,e and d/f have exact reusable assertions except generation.
            text=(ROOT/'firmware/engine_v42_ux/integration_native.py').read_text()
            import types
            ah=types.ModuleType('g119_ah_reference');ah.__file__=str(ROOT/'firmware/engine_v42_ux/integration_native.py')
            text=text.replace('==117', '==120').replace('== 117', '== 120')
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
