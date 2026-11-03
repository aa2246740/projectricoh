"""Exercise the two final navigation loops at declared callee contracts."""
from pathlib import Path
import collections
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import ROOT, SOURCE, OUT, save, sha, record_inputs
from current_runtime import differential as d, runner


def prepare(generation, function, iterations, stable):
    r = runner(generation)
    g = d.BASE+r.e.symbols['g']['address']
    r.write(r.n, bytes(r.e.symbols['n']['size']))
    r.write(g, bytes(r.e.symbols['g']['size']))
    r.b.map(0x2022f000, bytes(4096))
    r.write(d.DATA, bytes(512))
    calls, states = collections.Counter(), []
    def hook(name, callback=None, result=0):
        def cb(b):
            calls[name] += 1
            return callback(b) if callback else result
        r.hook(name, cb)
    hook('view_owned', result=1)
    if function == 'ig_apply':
        r.write(r.n+2072, b'\1')
        r.write(g+864,b'\1\0\x08')
        r.w32(d.DATA+40,4)
        hook('ingress',result=1)
        hook('start_view',result=1)
        hook('list_bind')
        hook('eng_visible_rows',result=8)
        hook('finish',result=1)
        hook('release_view',result=1)
        def preview(b):
            slot=b.core.r[0]
            states.append(dict(slot=slot,sp=b.core.r[15],call=calls['preview_cached']))
            next_row=slot if stable and calls['preview_cached']>=iterations else 7 if slot==5 else 5
            r.write(0x2022f726,bytes([next_row]))
            return 0
        hook('preview_cached',preview)
        args=(0,0,d.DATA,d.DATA+256)
    else:
        r.write(r.n+549,bytes([0,1,1]))
        r.write(r.n+452,bytes([0,5]))
        r.write(r.n+519,bytes(range(6)))
        r.write(r.n+1507,bytes([251]*4+[5]*4))
        r.write(r.n+511,bytes(8))
        hook('panel_render.constprop.0')
        def current(b):
            tweak=r.read(r.n+511,8)
            b.write(b.core.r[0],tweak)
            return 0
        actual='eng_current' if generation==119 else 'eng_current.constprop.0'
        if generation==119:
            def current_old(b):
                b.write(b.core.r[0],r.read(r.n+452,51))
                b.write(b.core.r[1],r.read(r.n+511,8))
                return 0
            hook(actual,current_old)
        else:
            hook(actual,current)
        def parameter(b):
            sp=b.core.r[15]
            for i,v in enumerate((-5,5,0)):
                pointer=int.from_bytes(b.read(sp+4*i,4),'big')
                b.write(pointer,(v&0xffffffff).to_bytes(4,'big'))
            return 0
        hook('gxr2_parameter',parameter)
        def preview(b):
            row=int.from_bytes(b.read(b.core.r[1],1),'big')
            row=(row if row<128 else row-256)+5
            r.write(r.n+511,b.read(b.core.r[1],8))
            states.append(dict(row=row,sp=b.core.r[15],call=calls['eng_preview_saved']))
            next_row=row+1 if stable and calls['eng_preview_saved']>=iterations else 8 if row==5 else 6
            r.write(0x2022f726,bytes([next_row]))
            return 0
        if generation==120:
            hook('eng_preview_saved',preview)
        args=(5,)
    r.reset(0x120b)
    result=r.call(function,args,steps=max(20000,iterations*450))
    return dict(generation=generation,function=function,requested_iterations=iterations,
        stable_at_end=stable,stop=result['stop'],result=result['result'],abi_ok=result['abi_ok'],
        calls=dict(calls),states=states,edges=result['edges'],
        minimum_sp=min((row['sp'] for row in states),default=None),
        maximum_sp=max((row['sp'] for row in states),default=None),
        elf_sha256=sha(r.e.raw),engine_sha256=sha(r.e.engine['data']))


def main():
    cases=[]
    for function in ('ig_apply','a4_move'):
        for count in (1,16,64):
            row=prepare(120,function,count,True)
            assert row['stop']['reason']=='return',row['stop']
            actual=len(row['states'])
            assert actual==count,(function,count,actual)
            assert row['minimum_sp']==row['maximum_sp']
            assert row['abi_ok']
            cases.append(row)
        row=prepare(120,function,64,False)
        assert row['stop']['reason']!='return'
        assert len(row['states'])>64
        assert row['minimum_sp']==row['maximum_sp']
        cases.append(row)
    save('loop-cases.json',dict(status='CONFIRMED_NO_FIXED_ITERATION_BOUND',cases=cases,
        contracts='Only the named function body and ordinary RAM helpers execute. UI and successful transaction callees use explicit contracts; the native input byte changes at that transaction boundary.',
        reachability_evidence='research/ux_preview_dot_r5/native/coalescing-120-50mm-at1.json',
        limitation='This is instruction-level loop evidence. Continuous camera input and RTOS scheduling were not executed.'))
    record_inputs('loop-inputs.json')
    print('PASS loop checks:',[(row['function'],len(row['states']),row['stop']['reason']) for row in cases])


if __name__=='__main__':
    main()
