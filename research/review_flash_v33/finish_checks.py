"""Read-only image fault rejections, compiled stack comparison and evidence audit."""
import argparse
import contextlib
import io
import json
import re
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review as c
import artifacts as a
from host import module

def image_audit():
    audit=module(c.ROOT/'firmware/image_v33/audit.py','independent_image_auditor')
    args=argparse.Namespace(package=c.ROOT/'firmware/image_v33/local/reproduced-final-v33',official=a.STOCK,
        elf=c.ROOT/'firmware/resident_v33/local/resident/build/resident.elf',
        hooks=c.ROOT/'firmware/resident_v33/local/hooks.json',
        patch_manifest=c.ROOT/'firmware/resident_v33/local/resident/patch-manifest.json',stage2l=audit.REFERENCE)
    actual=audit.audit(args);assert actual['image_sha256']==c.digest(a.PACKAGE/'SD_ROOT/ilaunch3')
    c.write('full-image-audit.json',actual)
    record=json.loads((c.ROOT/'firmware/image_v33/local/verification-final/verification.json').read_text())
    assert record['image_sha256']==actual['image_sha256']
    rejections=[]
    for case in record['rejections']:
        argv=case['argv'];d=vars(args).copy()
        for key in ('package','official','elf','hooks','patch_manifest','stage2l'):
            flag='--'+key.replace('_','-')
            if flag in argv:d[key]=Path(argv[argv.index(flag)+1])
        assert '--report' in argv  # Do not forward it: the frozen fixture must stay untouched.
        try:audit.audit(argparse.Namespace(**d))
        except audit.Rejected as error:
            assert error.code==case['expected'],(case['case'],error.code,case['expected'])
            rejections.append(dict(case=case['case'],expected=case['expected'],observed=error.code,error=str(error)))
        else:raise AssertionError(('fault accepted',case['case']))
    assert len(rejections)==14
    # The final SD_ROOT checksum list intentionally covers all 30 camera files; manifest is separately frozen.
    lines=(a.PACKAGE/'SHA256SUMS').read_text().splitlines();seen=set()
    for line in lines:
        digest,name=line.split('  ',1);assert name not in seen;seen.add(name)
        assert c.digest(a.PACKAGE/name)==digest
    assert seen=={'SD_ROOT/'+p.name for p in (a.PACKAGE/'SD_ROOT').iterdir()}
    c.write('image-faults.json',dict(status='PASS',frozen_mutants_reaudited=14,no_builder_or_repack=True,
        final_camera_file_sums=30,manifest_sha256=c.digest(a.PACKAGE/'manifest.json'),rejections=rejections))
    print('PASS complete image audit, 14 frozen image fault rejections, 30 package sums',flush=True)

def stack():
    s=module(c.ROOT/'firmware/resident_v33/stack_checks.py','compiled_stack_model')
    out=c.LOCAL/'stack';out.mkdir(exist_ok=True);s.LOCAL=out
    paths={
      'v32':(c.ROOT/'firmware/resident_v32/local/product/m32r-lto/engine.elf',c.ROOT/'firmware/resident_v32/local/product/m32r-lto',c.ROOT/'firmware/resident_v32/local/resident/engine-services'),
      'r7':(c.ROOT/'firmware/engine_v33d/local/full-r7/engine.elf',c.ROOT/'firmware/engine_v33d/local/product/m32r-lto',c.ROOT/'firmware/engine_v33d/local/resident/engine-services'),
      'r9':(c.ROOT/'firmware/resident_v33/acceptance/local/full-r9/engine.elf',c.ROOT/'firmware/resident_v33/acceptance/local/product-r9/m32r-lto',c.ROOT/'firmware/resident_v33/acceptance/local/resident/engine-services')}
    resident=s.artifact('resident',c.ROOT/'firmware/resident_v33/local/resident/build/resident.elf',[c.ROOT/'firmware/resident_v33/local/resident/build'])
    oldresident=s.artifact('resident-v32',c.ROOT/'firmware/resident_v32/local/resident/build/resident.elf',[c.ROOT/'firmware/resident_v32/local/resident/build'])
    assert resident['frames']['rv_hook_observe']==oldresident['frames']['rv_hook_observe']==36
    entries={1:'ig_menu',6:'ig_panel_open',7:'ig_event',8:'ig_apply'};profiles={}
    for label,(elf,su,services) in paths.items():
        model=s.artifact(label,elf,[su,services])
        for name,targets in (
            ('svc',['core_call']),('pn_call',['rv_call']),('core_call',['rv_call']),('rv_call',['rv_service']),
            ('disarm',['grain_snapshot']),('eng_apply',['grain_snapshot']),
            ('read_object',['io_open','io_read','io_close']),('gxts_load',['io_open','io_read','io_close']),
            ('gxts_save',['io_open','io_read','io_write','io_close','io_remove','io_rename']),
            ('inspect',['verify','last_verify']),('ps_install',['verify']),('pn_ui_render',['pn_native_from_seed']),
            ('a4_finish',['io_open','io_read','io_write','io_close','io_remove','io_rename']),
            ('rpc',['rv_call']),('pn_address',['address'])):s.add(model,name,targets)
        frames=resident['frames'];prefix=68+sum(frames[n] for n in ('rv_hook_observe','rv_engine','rv_invoke'))
        combined={2:180,5:104,9:104};chains={}
        for hook,entry in entries.items():
            n,chain=s.peak(model,entry);combined[hook]=prefix+n;chains[hook]=chain
        combined[1]=max(combined[1],prefix+frames['rv_load']+max(s.peak(model,n)[0] for n in ('ig_init','ig_bootstrap')))
        profiles[label]=dict(modeled_hook_bytes=combined,chains=chains,unresolved_indirect=[n for n,v in model['indirect'].items() if v])
    assert profiles['r9']['modeled_hook_bytes']=={1:964,2:180,5:104,6:868,7:1216,8:824,9:104}
    oldraw=(c.ROOT/'firmware/resident_v32/local/product/candidates/full/GXRCE.DAT').read_bytes()
    oldmain=7504+((len(oldraw)+struct.unpack_from('>I',oldraw,116)[0]+3)&~3)
    c.write('stack.json',dict(status='PASS_BOUNDED_MODEL',profiles=profiles,
        resident_observer_frame_unchanged=True,previous_approved_full_main_request=oldmain,
        native_deep_stack_IRQ_and_task_baseline_included=False,device_stack_waterline_measured=False))
    print('PASS compiled stack models; v32/r7/r9 compared; global safety remains unproven',flush=True)

def counts():
    base=c.ROOT/'firmware/resident_v33/acceptance/local/r9-acceptance'
    reported=json.loads((c.ROOT/'firmware/resident_v33/local/recovery/final-test-counts.json').read_text())['r9']
    rows=[]
    for phase,want in reported['phases'].items():
        path=base/('run-'+phase+'.json');actual=json.loads(path.read_text())
        assert actual['status']=='PASS' and actual['host_runs']==want['host_runs']
        cases=actual['cases'];assert len(cases)==want['host_runs']
        assert sum(r['assertions'] for r in cases)==want['assertions']==actual['assertions']
        for row in cases:
            log=c.ROOT/'firmware/resident_v33/acceptance'/row['log']
            lines=log.read_text().rstrip().splitlines();assert lines[-1].startswith('OK ')
            assert int(re.search(r'assertions=(\d+)',lines[-1])[1])==row['assertions']
        rows.append(dict(phase=phase,runs=len(cases),assertions=actual['assertions']))
    assert sum(r['runs'] for r in rows)==2730
    c.write('builder-count-audit.json',dict(status='PASS_RECORDED_COUNT_ONLY',runs=2730,
        assertions=sum(r['assertions'] for r in rows),phases=rows,independently_reran_all_2730=False))
    print('PASS builder count/log consistency: 2730, separate from independent reruns',flush=True)

if __name__=='__main__':{'image':image_audit,'stack':stack,'counts':counts}[sys.argv[1]]()
