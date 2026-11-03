#!/usr/bin/python3
"""复用既有恢复执行，追踪 H50/H51/H52，工具源保持只读。"""
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
HERE=ROOT/'research/v310_resident'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-resident-r1')
sys.path.insert(0,str(HERE))
import fixtures_r2 as F


def run(name):
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert os.environ.get('GXR_EMULATOR_BATCH')=='1'
    fixture=F.prepare(name)
    path=ROOT/'research/body_v39/tests/recovery_path.py'
    source=path.read_text()
    old="    subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT, check=True)"
    assert source.count(old)==1
    source=source.replace(old,'    assert path.is_relative_to(LOCAL)')
    source=source.replace('str(path.relative_to(ROOT))','str(path)')
    source=source.replace("HERE.parent / 'evidence'", "HERE.parent / 'evidence_r2'")
    mod=types.ModuleType('thin_recovery');mod.__file__=str(path)
    sys.modules[mod.__name__]=mod;exec(compile(source,str(path),'exec'),mod.__dict__)
    mod.HOOK_WORDS.update(H50=0x2029ebc0,H51=0x202b1310,H52=0x202afe98)
    mod.LOCAL=TEMP/'r2-recovery'/name;mod.HERE=HERE/'tests_r2'
    import storage_run
    storage_run.OUT=TEMP/'r2-recovery-machine'/name
    label='r2-'+name.replace('_','-')
    args=argparse.Namespace(image=fixture['body'],label=label,elf=fixture['elf'],hold=[15],
          budget=150_000_000,serial=['8=0x5'],stop_at='confirm',card='official',confirm_keys=[])
    out=HERE/'evidence_r2'/name;start=time.monotonic();signal.alarm(1800)
    try:
        with (out/'recovery-run.log').open('w') as stream,contextlib.redirect_stdout(stream):
            mod.run(args)
    finally:signal.alarm(0)
    result=json.loads((HERE/'evidence_r2'/('recovery-'+label+'.json')).read_text())
    assert result['stop']=='confirm-stage reached inside the update UI',result['stop']
    assert not result['hooks_or_resident_executed'] and not result['pc_in_resident_window']
    assert result['card']['files']==29
    baseline=json.loads((ROOT/'research/v310_window/evidence/recovery-baseline.json').read_text())
    equal={k:result[k]==baseline[k] for k in ('counts','nand_commands','stop')}
    assert all(equal.values()),equal
    receipt=dict(status='PASS',variant=name,backend='batch emulator',steps=result['steps'],
                 seconds=time.monotonic()-start,hook_entries=0,new_hook_entries=0,
                 new_sites={k:hex(v) for k,v in mod.HOOK_WORDS.items() if k in ('H50','H51','H52')},
                 baseline_equal=equal,source_sha256=F.sha(path),
                 executed_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                 adaptations=['output/virtual medium paths only; add three new replacement words to observations'],
                 body_sha256=fixture['body_sha256'],elf_sha256=fixture['elf_sha256'],
                 timeout=1800,nice=os.getpriority(os.PRIO_PROCESS,0),endpoint='update confirmation only')
    (out/'recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    for name in sys.argv[1:]:run(name)
