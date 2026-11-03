"""Continue after the fully completed native cold, excluding its later host-check error."""
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from repro_flow import phase
from runtime import sha


def main():
    prefix='p1final-mount';engine=ROOT/'firmware/engine_v67_g155c';common=['--engine',engine,'--elf',engine/'candidate/local/boot-on/engine.elf']
    cold=json.loads((HERE/'evidence'/f'{prefix}-cold1.json').read_text())
    detail=json.loads((HERE/'evidence'/f'{prefix}-cold1-detail.json').read_text())
    assert cold['error'] is None and cold['boot']['stop']['reason']=='breakpoint'
    boot=[v for v in detail['calls'] if v['op']==257]
    assert len(boot)==1 and int(boot[0]['reply'][-8:],16)==1 and detail['final']['word']==2
    out=HERE/'evidence'/(prefix+'-resume-flow.json');assert not out.exists();rows=[]
    result=dict(status='RUNNING',phases=rows,dat_sha256=detail['dat_sha256'],
        completed_native_cold_receipt=prefix+'-cold1.json',completed_native_cold_sha256=sha((HERE/'evidence'/f'{prefix}-cold1.json').read_bytes()),
        excluded_failure='Later host-only non-pure04 replay reached an unsupported RTOS trap after the native cold had finished.',
        original_UI_record_prefix=prefix)
    target=HERE/'local'/(prefix+'-manual-accept-target.bin')
    def run(script,args,suffix,backend='c'):
        phase(script,args,prefix+'-'+suffix+'-resume-run',rows,backend)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    def accept(source,suffix,expected):
        run('accept.py',['--source',source,*common,'--name',prefix+'-'+suffix,'--expected',expected],suffix)
    def menu(source,cycle):
        name=prefix+'-menu'+str(cycle)
        run('probe.py',['--source',source,*common,'--mode','inspect','--name',name],name[len(prefix)+1:])
        m=json.loads((HERE/'evidence'/(name+'.json')).read_text())
        assert m['open_menu_W_T']==m['open_controls_W_T']==0
        assert m['first_menu']['levels']==m['first_controls']['levels']==m['final']['engine_levels']
        final=HERE/'local'/(name+'-final.pkl.z')
        accept(final,'menu'+str(cycle)+'-accept',target)
        for backend in ('c','python'):
            run('glyphs.py',['--source',HERE/'local'/(name+'-first-menu.pkl.z'),*common,
                '--name',name+'-glyphs'],'menu'+str(cycle)+'-glyphs-'+backend,backend)
        return final
    try:
        source=HERE/'local'/(prefix+'-cold1-session.pkl.z')
        accept(source,'cold1-accept',target)
        source=menu(source,1)
        run('probe.py',['--source',source,*common,'--mode','tweak-only','--name',prefix+'-tweak-only'],'tweak-only')
        source=HERE/'local'/(prefix+'-tweak-only-final.pkl.z')
        run('accept.py',['--source',source,*common,'--name',prefix+'-tweak-only-accept'],'tweak-only-accept')
        target=HERE/'local'/(prefix+'-tweak-only-accept-target.bin')
        run('probe.py',['--source',source,*common,'--mode','exit','--name',prefix+'-exit2'],'exit2')
        settings=HERE/'local'/(prefix+'-exit2-final-S-persistent.bin')
        run('cold_run.py',['--name',prefix+'-cold2','--unit','mount','--dat',ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT',
            '--settings-source',settings,'--capture-boot','--budget',650000000,'--timeout',14400],'cold2')
        source=HERE/'local'/(prefix+'-cold2-session.pkl.z');accept(source,'cold2-accept',target);menu(source,2)
        result['status']='PASS'
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
    finally:out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
