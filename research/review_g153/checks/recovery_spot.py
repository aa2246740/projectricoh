"""Run one cold-start recovery confirmation on the final body, with local outputs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import signal
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/review_g153'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g153-r1/recovery-confirm')

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==10
    TMP.mkdir(parents=True,exist_ok=True)
    os.environ['TMPDIR']=str(TMP)
    source=ROOT/'research/body_v39/tests/recovery_path.py'
    text=source.read_text()
    old="subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT, check=True)"
    assert text.count(old)==1
    text=text.replace(old,"assert path.is_relative_to(Path("+repr(str(TMP))+"))")
    old="dict(path=str(path.relative_to(ROOT)), sha256=sha(path.read_bytes()), files=len(files),"
    assert text.count(old)==1
    text=text.replace(old,"dict(path=str(path), sha256=sha(path.read_bytes()), files=len(files),")
    module=types.ModuleType('review_recovery_path');module.__file__=str(source)
    exec(compile(text,str(source),'exec'),module.__dict__)
    module.LOCAL=TMP
    module.HERE=OUT/'checks'
    args=argparse.Namespace(image=str(ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/ilaunch3'),
        label='review-g153-confirm',elf=str(ROOT/'research/v39_g153/local/body/local/resident/build/resident.elf'),
        hold=[15],budget=70000000,serial=['8=0x5'],stop_at='confirm',card='official',confirm_keys=[])
    start=time.time_ns();tick=time.monotonic()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('recovery confirmation')))
    signal.alarm(3600)
    try:
        module.run(args)
    finally:
        signal.alarm(0)
    result=json.loads((OUT/'evidence/recovery-review-g153-confirm.json').read_text())
    assert result['image_sha256']=='8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
    assert result['steps']==65975242 and 'inside the update UI' in result['stop']
    assert not result['hooks_or_resident_executed'] and not result['pc_in_resident_window']
    assert result['card']['files']==29
    receipt=dict(status='PASS',started_ns=start,ended_ns=time.time_ns(),seconds=time.monotonic()-tick,
                 pid=os.getpid(),backend='tools/gxr_emulator_batch native C',nice=os.getpriority(os.PRIO_PROCESS,0),
                 timeout=3600,steps=result['steps'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 executed_source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 modifications=['Only the temporary-medium location check and serialized medium path change.'],
                 image_sha256=result['image_sha256'],hook_entries=0)
    (OUT/'results/recovery-confirm-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
