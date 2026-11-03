"""Extra boundary probes using the documented registered control functions."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as V


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--backend', choices=('native', 'reference'), required=True)
    p.add_argument('--case', choices=('label-long', 'label-nul', 'label-unicode', 'label-pair', 'stop-watch-order', 'watch-stop-order'), required=True)
    p.add_argument('--real', action='store_true', help='Cold g155b/50mm flow to 50M, no CPU state patching')
    p.add_argument('--name', help='Fresh output prefix for a rerun')
    a = p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    os.environ['TMPDIR'] = str(V.TEMP); os.environ['GXR_STRICT_REFERENCE_ORACLE'] = 'legacy'
    sys.addaudithook(V.fence); signal.alarm(500 if a.real else 120)
    R = V.runner(); R.setup(a.backend)
    from native_controls import watch_point, stop_at, export_state
    suffix = '-real' if a.real else ''
    name = a.name or (a.case + suffix + '-' + a.backend)
    if not name.replace('-', '').replace('_', '').isalnum():
        raise ValueError('use a simple fresh output prefix')
    ctx = R.construct('release' if a.real else 'main', name)
    c = ctx.machine.cpu
    if not a.real:
        c.set_reg('psw', 0x80)
    address = 0x202b1210 if a.real else c.get_reg('pc')
    before = V.fingerprint(ctx)
    label = 'x' * 130 if a.case == 'label-long' else 'a\x00b' if a.case == 'label-nul' else 'order'
    if a.case == 'label-unicode':
        label = '中' * 50
    labels = ['x' * 130, 'a\x00b'] if a.case == 'label-pair' else [label]
    row = dict(backend=a.backend, case=a.case, initial_steps=c.steps, labels=labels)
    try:
        if a.case == 'stop-watch-order':
            stop_at(c, address); watch_point(ctx.machine, address, label)
        else:
            for label in labels:
                watch_point(ctx.machine, address, label)
            if a.case == 'watch-stop-order':
                stop_at(c, address)
        stop = c.run(50000000 if a.real else 1)
        row.update(status='ACCEPTED', stop=stop.to_dict())
    except Exception as error:
        row.update(status='ERROR', error=dict(type=type(error).__name__, message=str(error)))
    row['steps'] = c.steps
    try:
        row['state'] = V.fingerprint(ctx)
        row['flow'] = export_state(ctx.machine).get('flow')
    except Exception as error:
        row['audit_error'] = dict(type=type(error).__name__, message=str(error))
        row['flow'] = None
    if row['flow'] is not None:
        row['flow']['stop_after'] = sorted(row['flow']['stop_after'])
        row['flow']['return_sites'] = sorted(row['flow']['return_sites'])
        row['flow']['counts'] = dict(row['flow']['counts'])
        row['flow']['pending'] = {repr(k): v for k, v in row['flow']['pending'].items()}
    row['native'] = c._native_driver.stats() if c._native_driver else None
    ctx.machine.close()
    target = V.RUNS / ('control-' + name + '.json')
    assert not target.exists(); target.write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(case=a.case, backend=a.backend, status=row['status'], steps=row['steps'],
                          error=row.get('error'), counts=row['flow']['counts'] if row['flow'] else None)), flush=True)


if __name__ == '__main__':
    main()
