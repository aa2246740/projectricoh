"""Negative fixture for the proposed scheduler-point acceptance policy."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, load

def main():
    enable()
    snap=load(HERE/'adapters/snapshot.py','review_snapshot_negative')
    metrics=json.loads((HERE/'local/snapshot-cold/metrics.json').read_text())
    source=HERE/'local/snapshots'/metrics['cache_key']/'card.snap.z'
    out=HERE/'local/snapshot-negative';out.mkdir(parents=True,exist_ok=True)
    snap.outputs.declare_media(out)
    machine,meta=snap.load(source,mode='fast',medium=out/'source-working.img',allow_idle_task=True)
    try:
        before=snap.quiet(machine)
        # This is a labelled synthetic RAM fixture, never executed as firmware.
        machine.cpu.write(0x200d2594+4,(0).to_bytes(4,'big'))
        after=snap.quiet(machine)
        target=out/'task2-ready.snap.z'
        synthetic=snap.save(machine,target,'card',ROOT/'research/emulator_speed/local/card-seed.img')
    finally:machine.close()
    strict_rejected=False
    try:
        restored,_=snap.load(target,medium=out/'strict-working.img')
        restored.close()
    except ValueError:strict_rejected=True
    restored,_=snap.load(target,medium=out/'allowed-working.img',allow_idle_task=True)
    try:
        restored_quiet=snap.quiet(restored)
    finally:restored.close()
    emit(out/'result.json',dict(scope='synthetic acceptance-policy fixture only; no firmware execution',
         before=before,after=after,synthetic_accepted=synthetic['accepted'],
         strict_load_rejected=strict_rejected,allow_idle_task_load_succeeded=True,restored=restored_quiet,
         extra_ready_task=2))
    assert before['active_tasks']==[1,21] and restored_quiet['active_tasks']==[1,2,21]
    assert strict_rejected and not synthetic['accepted']
    print(json.dumps(dict(strict_rejected=strict_rejected,extra_ready_task_accepted_with_allow_flag=2)),flush=True)

if __name__=='__main__':main()
