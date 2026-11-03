"""Additional graph, retained-reference, range and binding counterexamples."""
import argparse,functools,importlib.util,json,os,signal,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
from edge_cases import loop


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',required=True);p.add_argument('--name',required=True)
    p.add_argument('--wrapper',choices=('before','after','code-before','code-after','default-before','genuine'))
    a=p.parse_args();R.setup(a.backend);signal.alarm(600)
    if a.wrapper:
        import devices
        path=R.ROOT/'research/v310_body/fix/emulator/nand_read_tail.py'
        spec=importlib.util.spec_from_file_location('extended_known_tail',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.install()
        original=devices.NAND.read
        def modified(base):
            @functools.wraps(base)
            def wrapped(self,address,size):
                data=base(self,address,size)
                return bytes([data[0]^1]) if address==0 and size==1 else data
            return wrapped
        def alter():
            if a.wrapper.startswith('code'):
                # One closure cell, like the actual read-tail function.
                original.__code__=modified(original.__closure__[0].cell_contents).__code__
            elif a.wrapper=='default-before':
                original.__defaults__=(None,)
            elif a.wrapper!='genuine':devices.NAND.read=modified(original)
        if not a.wrapper.endswith('after'):alter()
        ctx=R.construct('main',a.name)
        try:
            if a.wrapper.endswith('after'):alter()
            m,c=ctx.machine,ctx.machine.cpu;n=m.devices['nand'];n.command=0x30;n.cursor=0;n.row=3;n.pages[3]=b'\x55'+b'\xff'*2111
            c.write(0x27f00000,bytes.fromhex('20917000'));c.set_reg('pc',0x27f00000);c.set_reg('r1',0)
            stop=c.run(1);assert stop.reason=='max_steps'
            result=dict(wrapper=a.wrapper,r0=c.get_reg('r0'),state=R.fingerprint(ctx),model_revision=c.model_revision,
                        native=c._native_driver.stats() if c._native_driver else None)
            if a.backend=='native' and a.wrapper=='genuine':assert result['native']['instructions']==1,result
            if a.backend=='native' and a.wrapper!='genuine':assert not result['native'] or result['native']['instructions']==0,result
        finally:ctx.machine.close()
    else:
        cases={}
        def run_case(name,prepare):
            ctx=R.construct('main',a.name+'-'+name);c=loop(ctx)
            try:
                finish=prepare(ctx,c)
                assert c.run(19).reason=='max_steps'
                detail=finish()
                cases[name]=dict(detail=detail,state=R.fingerprint(ctx),native=c._native_driver.stats() if c._native_driver else None)
            finally:ctx.machine.close()
        def duplicate(ctx,c):
            ctx.machine.panel.chain(c)
            return lambda:None
        run_case('duplicate-panel',duplicate)
        def no_base(ctx,c):
            c.step_hook=None
            return lambda:None
        run_case('empty-chain',no_base)
        def retain(kind):
            def setup(ctx,c):
                m=ctx.machine
                if kind=='dict':held=m.devices['gpio'].inputs
                elif kind=='list':held=m.devices['serial'].tx
                elif kind=='set':held=m.panel.down
                elif kind in ('nested','nested-excluded-key'):
                    key='backend' if kind=='nested-excluded-key' else 'values'
                    m.devices['gpio'].extra={'nested':{key:[]}};held=m.devices['gpio'].extra['nested'][key]
                elif kind=='bytes':held=m.devices['gpio'].data
                else:held=m.panel.records['DOWN']
                assert c.run(7).reason=='max_steps'
                if kind=='dict':held[0xff7040a1]=(255,90)
                elif kind=='list':held.append(b'X')
                elif kind=='set':held.add('UP')
                elif kind in ('nested','nested-excluded-key'):held.append(71)
                elif kind=='bytes':held[0]=90
                else:held['column_mask']=2
                def finish():
                    live=(m.devices['gpio'].inputs if kind=='dict' else m.devices['serial'].tx if kind=='list' else m.panel.down if kind=='set' else m.devices['gpio'].extra['nested'][key] if kind in ('nested','nested-excluded-key') else m.devices['gpio'].data if kind=='bytes' else m.panel.records['DOWN'])
                    assert held is live
                    return dict(same_object=held is live,retained=R.sha(repr(held).encode()))
                return finish
            return setup
        for kind in ('dict','list','set','nested','nested-excluded-key','bytes','record'):run_case('retained-'+kind,retain(kind))
        def alias(ctx,c):
            g=ctx.machine.devices['gpio'];g.extra=g.inputs
            return lambda:dict(alias=g.extra is g.inputs)
        run_case('internal-alias',alias)
        for field in ('clock','pending'):
            for bits in (63,64,127,128):
                for sign in (1,-1):
                    value=sign*((1<<bits)-1)
                    def setup(ctx,c,value=value,field=field):
                        d=ctx.machine.devices['serial'] if field=='clock' else ctx.machine.devices['sio2']
                        setattr(d,field,value)
                        return lambda:dict(value=getattr(d,field))
                    run_case(field+'-'+str(bits)+'-'+str(sign).replace('-','n'),setup)
        result=dict(cases=cases)
    result['status']='PASS';result['backend']=a.backend
    target=R.RUNS/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',name=a.name,cases=len(result.get('cases',{})))))


if __name__=='__main__':main()
