#!/usr/bin/python3
"""Replay a real recovery checkpoint without altering any native return value."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import signal
import sys
import time
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')
BODY=ROOT/'research/v310_body'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--flow',choices=('official','v310'),required=True)
    p.add_argument('--backend',choices=('native','reference'),default='native')
    p.add_argument('--empty',action='store_true')
    p.add_argument('--hold-up',action='store_true')
    p.add_argument('--name',required=True)
    a=p.parse_args()
    target=HERE/'evidence'/(a.name+'.json');assert not target.exists()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    os.environ['TMPDIR']=str(TEMP)
    os.environ['GXR_FAST_BACKEND']=a.backend
    os.environ['GXR_FAST_MODEL_FIXES']='nand-word,preview-link,sd-long-response,nand-read-tail'
    sys.path.insert(0,str(ROOT/'tools/gxr_emulator_fast'))
    import storage_run,outputs
    from panel import Panel
    outputs.declare_media(TEMP)
    source=BODY/'fix/r3/local'/('recovery-fixed-'+a.flow+'-part14-final-state.pkl.z')
    saved=pickle.loads(zlib.decompress(source.read_bytes()))
    record=next(d['medium_record'] for t,d in zip(saved['cpu']['device_types'],saved['cpu']['devices']) if t=='SdHost')
    retained=next(base/(record['sha256']+'.img') for base in
        [BODY/'fix/r3/local/media',BODY/'fix/r2/local/media',BODY/'fix/local/media']
        if (base/(record['sha256']+'.img')).is_file())
    assert sha(retained.read_bytes())==record['sha256']
    working=TEMP/(a.name+'.img');assert not working.exists();shutil.copyfile(retained,working)
    m=storage_run.Machine(working);c=m.cpu
    panel=None
    if a.hold_up:
        panel=Panel(c,m.devices);panel.chain(c);m.panel=panel
        panel.set_key('UP',True)
    c.restore(saved['cpu']);c.set_mode('fast');c.set_batch(True)
    assert c.steps==7000000000
    assert {name:c.get_reg(name) for name in saved['cpu']['registers']}==saved['cpu']['registers']
    assert [(b,bytes(d),w) for b,d,w in c.regions]==saved['cpu']['regions']
    before_registers=dict(saved['cpu']['registers'])
    before_regions=[(b,sha(bytes(d))) for b,d,w in c.regions]
    source_gpio=next(d for t,d in zip(saved['cpu']['device_types'],saved['cpu']['devices']) if t=='GPIO')
    gpio_equal=m.devices['gpio'].snapshot()==source_gpio
    del saved['cpu']
    m.observer.ui_initializers.update(saved.get('ui_initializers',{}))
    if panel is None:
        panel=Panel(c,m.devices);panel.chain(c);m.panel=panel
    result=dict(flow=a.flow,backend=a.backend,name=a.name,source=str(source.relative_to(ROOT)),
        source_sha256=sha(source.read_bytes()),start=c.steps,
        medium_source=str(retained.relative_to(ROOT)),medium_sha256=record['sha256'],
        image_sha256=saved['image_sha256'],native_register_changes=[],native_RAM_changes=[],
        model_revisions=c.model_revision,library_sha256=sha(c.library_path.read_bytes()),
        runner_sha256=sha(Path(__file__).read_bytes()),nice=os.getpriority(os.PRIO_PROCESS,0),
        timeout=14400,events=[],segments=[],H50_H51_H52_hits={},resident_entries=0,
        declared_held_keys=['UP'] if a.hold_up else [],source_GPIO_restored_equal=bool(gpio_equal),
        panel_setup='UP before CPU/device restore, matching original resume driver' if a.hold_up else 'All keys released after restore; separate device-input variant')
    nand=m.devices['nand']
    if not a.empty:
        data=(BODY/'fix/r3/local/declared-T-AA.bin').read_bytes()
        assert len(data)==16384 and data[0]==0xaa
        old=dict(nand.pages)
        for i in range(8):
            page=41*64+i;raw=bytearray(old.get(page,b'\xff'*2112))
            raw[:2048]=data[i*2048:(i+1)*2048];nand.pages[page]=bytes(raw)
        assert {k for k in set(nand.pages)|set(old) if nand.pages.get(k)!=old.get(k)}<=set(range(2624,2632))
        assert all(nand.pages[2624+i][2048:]==old.get(2624+i,b'\xff'*2112)[2048:] for i in range(8))
        result['declared_T_sha256']=sha(data)
    else:result['declared_T_sha256']=None
    assert before_registers=={name:c.get_reg(name) for name in before_registers}
    assert before_regions==[(b,sha(bytes(d))) for b,d,w in c.regions]
    def integer(at,n=4):return int.from_bytes(c.read(at,n),'big')
    locations=[(0x20088040,'T-read-entry'),(0x20088074,'T-read-return'),
               (0x2007785c,'T-commit-entry'),(0x2008a9bc,'T-write-return'),
               (0x200778cc,'T-commit-return'),(0x2036fa50,'all-components-return'),
               (0x2036db70,'success-return-a'),(0x2036dba4,'success-return-b'),
               (0x2036fa90,'error-page-return')]
    for at,label in locations:
        prior=c.breakpoints.get(at)
        def observed(cpu,at=at,label=label,prior=prior):
            stopped=prior(cpu) if prior else False
            T=integer(0x200c0d9c);data=c.read(T,16384)
            result['events'].append(dict(label=label,step=cpu.steps,pc=hex(at),r0=cpu.get_reg('r0'),
                lr=hex(cpu.get_reg('lr')),T_sha256=sha(data),first_byte=data[0],
                checksum=int.from_bytes(data[-4:],'big')))
            return stopped
        c.add_breakpoint(at,observed)
    for at,label in [(0x2029ebc0,'H50'),(0x202b1310,'H51'),(0x202afe98,'H52'),(0x2005276c,'resident')]:
        prior=c.breakpoints.get(at)
        def hit(cpu,label=label,prior=prior):
            result['H50_H51_H52_hits'][label]=result['H50_H51_H52_hits'].get(label,0)+1
            return prior(cpu) if prior else False
        c.add_breakpoint(at,hit)
    began=time.monotonic();stop=None
    signal.alarm(14400)
    try:
        while c.steps<7500000000:
            before=c.steps;start=time.monotonic();stop=c.run(min(25000000,7500000000-c.steps));c.materialize_native()
            result['segments'].append(dict(start=before,end=c.steps,seconds=time.monotonic()-start,stop=stop.to_dict()))
            print(json.dumps(dict(name=a.name,step=c.steps,pc=hex(c.get_reg('pc')),reason=stop.reason)),flush=True)
            if stop.reason!='max_steps':break
        result.update(steps=c.steps,pc=hex(c.get_reg('pc')),stop=stop.to_dict(),seconds=time.monotonic()-began,
            r0=c.get_reg('r0'),ui_initializers=m.observer.ui_initializers,
            NAND_programs=sum(v==0x10 for v in nand.commands),NAND_pages=len(nand.pages),
            SD_counts=dict(m.sd.counts),native_stats=c._native_driver.stats() if c._native_driver else None,
            batch_stats=dict(c.batch_stats))
        final=c.snapshot()
        path=HERE/'local'/(a.name+'-end.pkl.z')
        path.write_bytes(zlib.compress(pickle.dumps(dict(cpu=final,events=result['events'],
            ui_initializers=m.observer.ui_initializers),protocol=4),3))
        result['final_snapshot_sha256']=sha(path.read_bytes())
        result['final_snapshot']=str(path.relative_to(ROOT))
        nand_path=HERE/'local'/(a.name+'-nand.json')
        nand_path.write_text(json.dumps({str(k):bytes(v).hex() for k,v in sorted(nand.pages.items())})+'\n')
        result['final_NAND_sha256']=sha(nand_path.read_bytes())
        assert stop.reason=='breakpoint' and c.get_reg('pc')==0x2005ccf0
        commit=[e for e in result['events'] if e['label']=='T-commit-return']
        components=[e for e in result['events'] if e['label']=='all-components-return']
        success=[e for e in result['events'] if e['label'].startswith('success-return')]
        if a.empty:
            assert commit[-1]['r0']==0xffffffff and components[-1]['r0']!=0 and not success
            result['status']='EXPECTED_EMPTY_T_FAILURE'
        else:
            assert commit[-1]['r0']==0 and components[-1]['r0']==0 and success
            result['status']='PASS'
        assert not result['H50_H51_H52_hits']
    except BaseException as exc:
        result.update(status='ERROR',error=dict(type=type(exc).__name__,message=str(exc)),steps=c.steps)
        raise
    finally:
        signal.alarm(0)
        target.write_text(json.dumps(result,indent=2)+'\n')
        m.close()


if __name__=='__main__':main()
