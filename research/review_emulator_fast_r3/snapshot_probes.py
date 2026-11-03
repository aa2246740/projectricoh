"""Registered controls only: recipe identity and live ready-hold restore."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as V


def rebound(ctx, S):
    if hasattr(ctx, 'identity_bound'):
        del ctx.identity_bound
    ctx.identity_bound = S.identity(ctx)
    return ctx.identity_bound


def recipe_key(backend, name, unit_off=False):
    R = V.runner(); R.setup(backend)
    import snapshots as S
    from native_controls import engine_watch, export_state
    symbols = R.ROOT / 'firmware/resident_v310_g155/local/resident/symbols.log'
    address = next(int(line.split()[0], 16) for line in symbols.read_text().splitlines()
                   if len(line.split()) >= 5 and line.split()[-1] == 'rv_engine')
    contexts = []
    def context(name, stop):
        ctx = R.construct('main' if unit_off else 'release', name); contexts.append(ctx)
        engine_watch(ctx.machine, address, stop_on_return=stop)
        rebound(ctx, S)
        return ctx
    old = context(name + '-old-' + backend, True)
    target = context(name + '-target-' + backend, False)
    before = V.fingerprint(target)
    key_old = S.hash_value_reference(S.identity(old))
    key_target = S.hash_value_reference(S.identity(target))
    old.machine.cpu.run(19)
    old.controls = __import__('native_controls').export_controls(old.machine)
    path = V.LOCAL / (name + '-recipe-' + backend + '.snap.z')
    S.save(old, path)
    result = dict(backend=backend, old_key=key_old, target_key=key_target,
                  keys_equal=key_old == key_target,
                  target_stop_after_before=sorted(export_state(target.machine)['flow']['stop_after']))
    try:
        result['restore'] = S.restore(target, path)
        result['accepted'] = True
    except Exception as error:
        result['accepted'] = False
        result['error'] = dict(type=type(error).__name__, message=str(error))
    result['target_stop_after_after'] = sorted(export_state(target.machine)['flow']['stop_after'])
    result['target_steps_after'] = target.machine.cpu.steps
    result['target_changed'] = V.fingerprint(target) != before
    target_path = V.RUNS / (name + '-recipe-' + backend + '.json')
    target_path.write_text(json.dumps(result, indent=2) + '\n')
    if result['accepted'] and not unit_off:
        # Prove the wrong recipe changes an actual firmware stop, not just a key.
        c = target.machine.cpu
        try:
            stop = c.run(203000000 - c.steps)
            result['restored_run'] = dict(steps=c.steps, stop=stop.to_dict(), state=V.fingerprint(target))
        except Exception as error:
            result['restored_run'] = dict(steps=c.steps, error=dict(type=type(error).__name__, message=str(error)))
        target_path.write_text(json.dumps(result, indent=2) + '\n')
        baseline = context(name + '-baseline-' + backend, False)
        c = baseline.machine.cpu; stop = c.run(203000000)
        result['correct_recipe_run'] = dict(steps=c.steps, stop=stop.to_dict(), state=V.fingerprint(baseline))
    target_path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('restore', 'restored_run', 'correct_recipe_run')}), flush=True)
    for ctx in contexts:
        ctx.machine.close()


def ready_hold(backend, name, short=False):
    R = V.runner(); R.setup(backend)
    import snapshots as S
    from native_controls import export_controls
    ctx = R.construct('release', name + '-old')
    rows = []
    for end in (10000, 1000000, 5000000, 10000000, 20000000, 30000000):
        ctx.machine.cpu.run(end - ctx.machine.cpu.steps)
        controls = export_controls(ctx.machine)
        rows.append(dict(steps=end, controls={k: [x.hex() for x in v] for k, v in controls.items()}))
        if controls.get('held_ready'):
            break
    result = dict(probes=rows, found=bool(controls.get('held_ready')))
    if result['found']:
        ctx.controls = controls
        path = V.LOCAL / (name + '.snap.z')
        result['saved'] = S.save(ctx, path)
        expected = V.fingerprint(ctx)
        fresh = R.construct('release', name + '-restored')
        try:
            result['restore'] = S.restore(fresh, path)
            result['accepted'] = True
        except Exception as error:
            result['accepted'] = False
            result['error'] = dict(type=type(error).__name__, message=str(error))
        result['live_controls_before'] = {k: [x.hex() for x in v] for k, v in controls.items()}
        result['live_controls_after'] = {k: [x.hex() for x in v] for k, v in export_controls(fresh.machine).items()}
        result['actual_state_equal'] = V.fingerprint(fresh) == expected
        (V.RUNS / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        if result['accepted']:
            result['continuations'] = []
            for n in ((13,) if short else (13, 1000000, 30000000)):
                a = ctx.machine.cpu.run(n)
                try:
                    b = fresh.machine.cpu.run(n)
                except Exception as error:
                    result['continuations'].append(dict(old_steps=ctx.machine.cpu.steps,
                        restored_steps=fresh.machine.cpu.steps,
                        error=dict(type=type(error).__name__, message=str(error))))
                    break
                result['continuations'].append(dict(
                    old_steps=ctx.machine.cpu.steps, restored_steps=fresh.machine.cpu.steps,
                    old_stop=a.to_dict(), restored_stop=b.to_dict(),
                    equal=V.fingerprint(ctx) == V.fingerprint(fresh),
                    old_state=V.fingerprint(ctx), restored_state=V.fingerprint(fresh)))
        fresh.machine.close()
    ctx.machine.close()
    (V.RUNS / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('restore', 'continuations')}), flush=True)


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    sys.addaudithook(V.fence); os.environ['TMPDIR'] = str(V.TEMP)
    signal.alarm(1700)
    p = argparse.ArgumentParser(); p.add_argument('kind', choices=('recipe', 'recipe-off', 'hold'))
    p.add_argument('--name', required=True)
    p.add_argument('--short', action='store_true')
    p.add_argument('--backend', choices=('native', 'reference'), default='native'); a = p.parse_args()
    ready_hold(a.backend, a.name, a.short) if a.kind == 'hold' else recipe_key(a.backend, a.name, a.kind == 'recipe-off')


if __name__ == '__main__':
    main()
