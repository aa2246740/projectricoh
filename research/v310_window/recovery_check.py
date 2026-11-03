#!/usr/bin/python3
"""Reuse the existing recovery execution with this task's output locations."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')
sys.path.insert(0,str(HERE))
import fixtures as F


def run(name):
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert os.environ.get('GXR_EMULATOR_BATCH')=='1'
    fixture=F.prepare(name)
    path=ROOT/'research/body_v39/tests/recovery_path.py'
    text=path.read_text()
    old="    subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT, check=True)"
    assert text.count(old)==1;text=text.replace(old,'    assert path.is_relative_to(LOCAL)')
    text=text.replace('str(path.relative_to(ROOT))','str(path)')
    mod=types.ModuleType('window_recovery');mod.__file__=str(path)
    sys.modules[mod.__name__]=mod;exec(compile(text,str(path),'exec'),mod.__dict__)
    mod.LOCAL=TEMP/'recovery'/name
    mod.HERE=HERE/'tests'
    import storage_run
    storage_run.OUT=TEMP/'recovery-machine'/name
    label=name.replace('_','-')
    args=argparse.Namespace(image=fixture['body'],label=label,elf=fixture['elf'],hold=[15],
          budget=150_000_000,serial=['8=0x5'],stop_at='confirm',card='official',confirm_keys=[])
    out=HERE/'evidence'/name;out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();signal.alarm(1800)
    try:
        with (out/'recovery-run.log').open('w') as stream,contextlib.redirect_stdout(stream):
            mod.run(args)
    finally:signal.alarm(0)
    result=json.loads((HERE/'evidence'/('recovery-'+label+'.json')).read_text())
    assert result['stop']=='confirm-stage reached inside the update UI',result['stop']
    assert not result['hooks_or_resident_executed'] and not result['pc_in_resident_window']
    assert result['card']['files']==29
    receipt=dict(status='PASS',name=name,steps=result['steps'],seconds=time.monotonic()-start,
                 source=str(path.relative_to(ROOT)),source_sha256=F.sha(path),
                 executed_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 adaptations=['Virtual-medium location check and absolute medium path only.'],
                 body_sha256=fixture['body_sha256'],elf_sha256=fixture['elf_sha256'],
                 hook_entries=0,timeout=1800,nice=os.getpriority(os.PRIO_PROCESS,0))
    if name!='baseline':
        baseline=json.loads((HERE/'evidence/recovery-baseline.json').read_text())
        keys=['counts','nand_commands','stop']
        receipt['baseline_equal']={k:result[k]==baseline[k]for k in keys}
        receipt['arrival_step_matches_baseline']=result['steps']==baseline['steps']
        assert all(receipt['baseline_equal'].values()),receipt['baseline_equal']
    (out/'recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k]for k in ['status','name','steps','seconds']}),flush=True)


if __name__=='__main__':
    for name in sys.argv[1:]:run(name)
