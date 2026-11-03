"""Observe the legacy user-entry record rule through real selection and restart."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from repro_flow import phase
from runtime import Runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',default='legacy-user')
    parser.add_argument('--resume-controls',type=Path)
    parser.add_argument('--controls-receipt',type=Path)
    options=parser.parse_args()
    if options.resume_controls:options.resume_controls=options.resume_controls.resolve()
    if options.controls_receipt:options.controls_receipt=options.controls_receipt.resolve()
    name=options.name
    engine=ROOT/'firmware/engine_v63_g154'
    elf=engine/'candidate/local/full-r13/engine.elf'
    common=['--engine',engine,'--elf',elf]
    rows=[]
    out=HERE/'evidence'/(name+'-flow.json')
    assert not out.exists()
    result=dict(status='OPEN',layer='模拟器实测',phases=rows,native_state_presets=[])
    def run(script,args,suffix):
        phase(script,args,name+'-'+suffix+'-run',rows)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    try:
        if options.resume_controls is None:
            run('probe.py',['--mode','choose','--name',name+'-choose','--source',
                HERE/'local/repro-g154-first-menu-first-menu.pkl.z',*common,'--kind','user','--number',2],'choose')
            run('probe.py',['--mode','tweak-only','--name',name+'-controls','--source',
                HERE/'local'/(name+'-choose-final.pkl.z'),*common,'--kind','user','--number',2],'controls')
        controls_source=options.resume_controls or HERE/'local'/(name+'-controls-final.pkl.z')
        controls_path=options.controls_receipt or HERE/'evidence'/(name+'-controls.json')
        controls=json.loads(controls_path.read_text())
        before=controls['final']
        assert before['applied_user']==2
        assert before['engine_levels']!=controls['first_menu']['engine_levels']
        assert before['record']=='00'*40
        run('accept.py',['--source',controls_source,*common,
            '--name',name+'-manual-accept','--record-optional'],'manual-accept')
        settings=ROOT/controls['settings']['persistent_path']
        run('cold_run.py',['--name',name+'-cold','--unit','mount',
            '--dat',ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT',
            '--image',ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3',
            '--settings-source',settings,'--budget',250000000,'--timeout',10800],'cold')
        run('probe.py',['--mode','inspect','--name',name+'-menu','--source',
            HERE/'local'/(name+'-cold-session.pkl.z'),*common,'--kind','user','--number',2],'menu')
        menu=json.loads((HERE/'evidence'/(name+'-menu.json')).read_text())
        assert menu['first_menu']['applied_user']==0 and menu['first_menu']['slot']==4
        r=Runtime(HERE/'local'/(name+'-menu-first-menu.pkl.z'),name+'-cache',engine,elf)
        try:
            import struct
            saved_levels=list(struct.unpack('>10h',r.cpu.read(r.at('n.ui.saved')+20,20)))
        finally:r.machine.close()
        assert saved_levels!=before['engine_levels']
        result.update(status='OBSERVED_LIMITATION',manual_levels=before['engine_levels'],
            record_after_manual=before['record'],first_menu=menu['first_menu'],
            user_2_cached_after_restart=saved_levels,
            scope='This demonstrates the legacy user-entry limit. It does not identify a builtin HC BW loss.')
    finally:
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
