#!/usr/bin/python3
"""Run the existing recovery check with task-owned outputs and all hooks observed."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--budget',type=int,default=2_000_000_000)
    p.add_argument('--confirm-only',action='store_true')
    p.add_argument('--card-image',type=Path)
    p.add_argument('--timeout',type=int,default=7200)
    a=p.parse_args()
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert a.name.replace('-','').isalnum()
    path=ROOT/'research/body_v39/tests/recovery_path.py'
    spec=importlib.util.spec_from_file_location('v310_recovery_reference',path)
    R=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    # The original tool is read-only. Rebind only this process's paths.
    R.HERE=HERE/'runner'
    R.LOCAL=TEMP/'recovery'
    R.HOOK_WORDS.update(H50=0x2029ebc0,H51=0x202b1310,H52=0x202afe98)
    if a.card_image:
        original_files=R.official_files
        def candidate_files():
            files=original_files()
            files['ilaunch3']=a.card_image.read_bytes()
            return files
        R.official_files=candidate_files
    sys.path.insert(0,str(HERE))
    from cold_run import make_medium
    def make_recovery_medium(path,files):
        record=make_medium(path,files)
        import fat_image as F
        # Match the original recovery fixture's lowercase base-name metadata.
        with path.open('r+b') as stream:
            for i,name in enumerate(sorted(files)):
                base,_,ext=name.partition('.')
                flags=(8 if base.islower() else 0)|(16 if ext.islower() else 0)
                stream.seek((F.START+1+2*F.FAT_SECTORS)*F.SECTOR+32*i+12)
                stream.write(bytes([flags]))
        record.update(sha256=sha(path.read_bytes()),inspection=F.inspect(path),
                      base_case='preserve archive names')
        return record
    R.make_card=make_recovery_medium
    original=R.Machine
    holder={}
    class RecordedMachine(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            holder['machine']=self
            run_cpu=self.cpu.run
            previous_stop=None
            def guarded_run(*run_args,**run_kwargs):
                nonlocal previous_stop
                result=run_cpu(*run_args,**run_kwargs)
                location=(self.cpu.steps,self.cpu.get_reg('pc'))
                negative_ui=(result.reason=='breakpoint' and location[1]==0x2005ccf0
                             and self.cpu.get_reg('r0') & 0x80000000)
                repeated=(result.reason=='breakpoint' and previous_stop==location)
                previous_stop=location if result.reason=='breakpoint' else None
                if negative_ui or repeated:
                    terminal=dict(reason='native UI initialization returned a negative result'
                                  if negative_ui else 'breakpoint repeated without instruction progress',
                                  steps=location[0],pc=hex(location[1]),
                                  registers={f'r{i}':self.cpu.get_reg(f'r{i}') for i in range(16)},
                                  complete=False)
                    (HERE/'evidence'/f'recovery-{a.name}-terminal.json').write_text(
                        json.dumps(terminal,indent=2)+'\n')
                    raise RuntimeError(terminal['reason'])
                return result
            self.cpu.run=guarded_run
            for at,label in ((0x2036c9e4,'confirm'),(0x2036d4e8,'update-ui'),(0x200a40b4,'file-open')):
                previous=self.cpu.breakpoints.get(at)
                def observe(cpu,at=at,label=label,previous=previous):
                    old=previous(cpu) if previous else False
                    event=dict(label=label,step=cpu.steps)
                    if label=='file-open':
                        event['path']=cpu.read(cpu.get_reg('r4'),64).split(b'\0',1)[0].decode('latin-1')
                    print(json.dumps(event),flush=True)
                    return old
                self.cpu.add_breakpoint(at,observe)
        def close(self):
            flash=self.devices['nand']
            pages={str(k):sha(v) for k,v in sorted(flash.pages.items())}
            state=dict(page_hashes=pages,page_count=len(pages),
                       programmed_pages=sum(any(b!=255 for b in v) for v in flash.pages.values()),
                       nand_commands=dict(Counter(flash.commands)),
                       state=int.from_bytes(self.cpu.read(0x205d9c00,4),'big'),
                       pc=hex(self.cpu.get_reg('pc')),steps=self.cpu.steps,
                       complete=False,
                       completion_basis='Confirmation, a budget stop, or a native error does not prove update completion.')
            (HERE/'evidence'/f'recovery-{a.name}-flash.json').write_text(json.dumps(state,indent=2)+'\n')
            # Preserve final virtual NAND bytes under local for independent comparison.
            out=HERE/'local'/f'recovery-{a.name}-nand.json'
            out.write_text(json.dumps({str(k):bytes(v).hex() for k,v in sorted(flash.pages.items())})+'\n')
            super().close()
    R.Machine=RecordedMachine
    target=HERE/'evidence'/f'recovery-{a.name}.json'
    assert not target.exists()
    signal.alarm(a.timeout)
    def checkpoint(signum,frame):
        while frame and not (frame.f_code.co_name=='run' and frame.f_globals.get('__name__')=='v310_recovery_reference'):
            frame=frame.f_back
        if frame and frame.f_globals.get('__name__')=='v310_recovery_reference':
            values=frame.f_locals
            result={key:values.get(key) for key in ('counts','phase','segments','rows')}
            (HERE/'evidence'/f'recovery-{a.name}-progress.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(dict(checkpoint=a.name,counts=result['counts'],phase=result['phase'])),flush=True)
    signal.signal(signal.SIGUSR1,checkpoint)
    try:
        R.run(SimpleNamespace(image=str(a.image),label=a.name,
             elf=str(ROOT/'firmware/resident_v310_g155/local/resident/resident.elf'),
             hold=[15],serial=['8=0x5'],card='official',stop_at='confirm',
             confirm_keys=[] if a.confirm_only else [18,24],budget=a.budget))
    except BaseException as exc:
        (HERE/'evidence'/f'recovery-{a.name}-error.json').write_text(json.dumps(dict(
            type=type(exc).__name__,message=str(exc),source_sha256=sha(path.read_bytes())),indent=2)+'\n')
        raise
    finally:
        signal.alarm(0)


if __name__=='__main__':
    main()
