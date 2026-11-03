"""Fixed MAIN-to-candidate plus the retained complete ADJ instruction window."""
import argparse
import copy
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, TOOLS, LOCAL, digest, emit, enable, environment, load, private, sha, usage, verify_inputs


TOOLS = Path(__file__).resolve().parent

def binding(snap, profile, card, meta):
    return {'format': 'speedlab-snapshot-1', 'card_sha256': sha(card) if card else None,
            'runtime': {'python': sys.version, 'machine': platform.machine(), 'platform': platform.platform()},
            'machine_identity': snap.identity(card),
            'frozen_input_identity': verify_inputs(), 'batch_input_identity': sha(ROOT/'research/speed_hillclimb/BATCH_INPUTS.json'),
            'adapter_files': {str(p.relative_to(ROOT)): sha(p) for p in
                              [Path(__file__), TOOLS / 'common.py', TOOLS / 'adapters/snapshot.py']},
            'candidate_steps': meta['steps'], 'candidate_state': meta['state_hash'],
            'profile': profile, 'mode': 'fast', 'batch': True, 'sequence': [['ADJ', True, 120000], ['ADJ', False, 3000000]]}

def load_cached(snap, path, bound, medium, allow_candidate=False):
    entry = json.loads(path.with_suffix('.entry.json').read_text())
    if entry['binding'] != bound or entry['key'] != digest(bound):
        raise ValueError('cached snapshot identity differs; cold rebuild required')
    if sha(path) != entry['snapshot_sha256'] or sha(path.with_suffix('.json')) != entry['metadata_sha256']:
        raise ValueError('cached snapshot receipt differs; cold rebuild required')
    machine,metadata=snap.load(path, mode='fast', medium=medium, allow_idle_task=allow_candidate)
    machine.cpu.set_batch(True)
    return machine,metadata

def proof(snap, machine, flow, segments, boot):
    return {'state': snap.state_hash(machine), 'observations': snap.value_hash(snap.observer_data(machine)),
            'flow_hash': snap.value_hash(flow.rows), 'flow': flow.rows,
            'flow_pending_hash': snap.value_hash(flow.pending), 'flow_counts': dict(flow.counts),
            'flow_open_calls': flow.open_calls(), 'segments': segments,
            'machine_events_hash': snap.value_hash(machine.events),
            'pending_returns_hash': snap.value_hash(machine.pending_returns),
            'panel_events': machine.panel.events, 'start_step': boot['steps'], 'end_step': machine.cpu.steps,
            'boot': boot, 'ui_state': int.from_bytes(machine.cpu.read(0x205D9C00, 4), 'big'),
            'completed_all_segments': len(segments) == 2 and all(s['stop']['reason'] == 'max_steps' for s in segments)}

def state_mutations(snap, machine):
    original = snap.state_hash(machine)
    checks = {}
    old = machine.cpu.get_reg('r0')
    machine.cpu.set_reg('r0', old ^ 1)
    checks['cpu'] = snap.state_hash(machine)['cpu'] != original['cpu']
    machine.cpu.set_reg('r0', old)
    address, data, writable = next(row for row in machine.cpu.regions if row[2] and len(row[1]) > 8)
    data[-1] ^= 1
    checks['memory'] = snap.state_hash(machine)['memory'] != original['memory']
    data[-1] ^= 1
    saved = copy.deepcopy(machine.devices['irq'].pending)
    machine.devices['irq'].pending.append(255)
    checks['devices'] = snap.state_hash(machine)['devices'] != original['devices']
    machine.devices['irq'].pending = saved
    original_observation = snap.value_hash(snap.observer_data(machine))
    machine.observer.counts['speedlab_mutation'] += 1
    checks['observations'] = snap.value_hash(snap.observer_data(machine)) != original_observation
    del machine.observer.counts['speedlab_mutation']
    machine.panel.down.add('ADJ')
    checks['panel_down'] = snap.state_hash(machine)['devices'] != original['devices']
    machine.panel.down.remove('ADJ')
    checks['restored_after_mutations'] = snap.state_hash(machine) == original and snap.value_hash(snap.observer_data(machine)) == original_observation
    return {'passed': all(checks.values()), 'checks': checks}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('card', 'no-card'), default='card')
    parser.add_argument('--origin', choices=('cold', 'restore'), default='cold')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-candidate', action='store_true')
    parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args()
    enable()
    out = private(args.output); out.mkdir(parents=True, exist_ok=True)
    subprocess.run(['/bin/df','-h','/Volumes/Workspace'],check=True)
    began = time.monotonic()
    metrics = {'environment': environment(), 'profile': args.profile, 'origin': args.origin}
    snap = load(TOOLS / 'adapters/snapshot.py', 'speedlab_snapshot')
    import storage_run,input_run
    storage_run.OUT=out/'storage'; input_run.OUT=out/'input'
    snap.outputs.declare_media(out)
    from input_run import Flow
    old_meta = json.loads((ROOT / 'tools/gxr_emulator/local/speed' / (args.profile + '.snap.json')).read_text())
    card = ROOT / 'research/emulator_speed/local/card-seed.img' if args.profile == 'card' else None
    approved=json.loads((ROOT/'research/speed_hillclimb/BATCH_INPUTS.json').read_text())
    if any(sha(ROOT/name)!=value for name,value in approved['files'].items()):
        raise ValueError('reviewed batch runtime identity changed')
    bound = binding(snap, args.profile, card, old_meta)
    key = digest(bound)
    cache = LOCAL / 'snapshots' / key
    target = cache / (args.profile + '.snap.z')
    task_events = []
    machine = None
    try:
        if args.origin == 'cold':
            machine = snap.cold(card, mode='fast', medium=out / 'medium.img')
            machine.cpu.set_batch(True)
            # Extra read-only task observations do not alter Observer or saved model state.
            address = 0x200D2594 + 4 * 20
            def task_state(addr, data):
                if addr <= address < addr + len(data):
                    task_events.append({'step': machine.cpu.steps, 'writer_pc': machine.cpu.get_reg('pc'),
                                        'task': machine.task(), 'address': addr, 'raw': data.hex()})
            machine.cpu.add_write_trace(address, address + 4, task_state)
            remaining = old_meta['steps']
            while remaining:
                count = min(remaining, 1000000)
                snap.run_steps(machine, count)
                remaining -= count
                print(json.dumps({'cold_step': machine.cpu.steps, 'target': old_meta['steps']}), flush=True)
            if snap.state_hash(machine) != old_meta['state_hash']:
                raise ValueError('cold boot differs from retained complete candidate state')
            cache.mkdir(parents=True, exist_ok=True)
            valid = False
            try:
                entry = json.loads(target.with_suffix('.entry.json').read_text())
                saved = json.loads(target.with_suffix('.json').read_text())
                valid = (entry['binding'] == bound and entry['key'] == key and
                         entry['snapshot_sha256'] == sha(target) and entry['metadata_sha256'] == sha(target.with_suffix('.json')))
                if saved.get('medium'):
                    medium_path = snap.private(target.parent / saved['medium']['file'])
                    valid = valid and sha(medium_path) == saved['medium']['sha256']
            except (OSError, ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                existing = list(cache.glob(args.profile + '.snap.*'))
                if existing:
                    rejected = cache / ('rejected-' + str(len(list(cache.glob('rejected-*'))) + 1))
                    rejected.mkdir()
                    for item in existing: item.rename(rejected / item.name)
                metadata = snap.save(machine, target, args.profile, card, snap.identity(card))
                emit(target.with_suffix('.entry.json'), {'key': key, 'binding': bound,
                     'snapshot_sha256': sha(target), 'metadata_sha256': sha(target.with_suffix('.json'))})
        else:
            machine, metadata = load_cached(snap, target, bound, out / 'medium.img', args.allow_candidate)
        ready = time.monotonic()
        boot = {'steps': machine.cpu.steps, 'state': snap.state_hash(machine),
                'observations': snap.value_hash(snap.observer_data(machine)),
                'machine_events_hash': snap.value_hash(machine.events),
                'pending_returns_hash': snap.value_hash(machine.pending_returns), 'quiet': snap.quiet(machine)}
        if args.mutations:
            result = state_mutations(snap, machine)
            emit(out / 'state-mutations.json', result)
            if not result['passed']:
                raise ValueError('full-state mutation selfcheck failed')
        flow = Flow(machine)
        segments = []
        for down, count in ((True, 120000), (False, 3000000)):
            machine.panel.set_key('ADJ', down)
            stop = snap.run_steps(machine, count)
            segments.append({'key': 'ADJ', 'down': down, 'requested': count,
                             'stop': stop.to_dict(), 'end_step': machine.cpu.steps})
        executed = time.monotonic()
        result = proof(snap, machine, flow, segments, boot)
        emit(out / 'result.json', result)
        emit(out / 'task21-observations.json', {'origin': args.origin, 'writes': task_events,
             'last_service': machine.observer.last_services.get(21),
             'task_creation': machine.observer.created_tasks.get(21),
             'task_entry': machine.observer.task_entry_records.get(21)})
        if machine.cpu.batch_stats.get('batch-steps',0)<=0 or machine.cpu.batch_stats.get('undeclared-hook-steps',0):
            raise ValueError('production snapshot workload did not use the reviewed declared batch chain')
        metrics.update(batch_stats=dict(machine.cpu.batch_stats), batch_input_identity=sha(ROOT/'research/speed_hillclimb/BATCH_INPUTS.json'), returncode=0, setup_seconds=ready - began, run_seconds=executed - ready,
                       wall_seconds=time.monotonic() - began, instruction_count=3120000 + (old_meta['steps'] if args.origin == 'cold' else 0),
                       cache_key=key, candidate_accepted=old_meta['accepted'], **usage())
        emit(out / 'metrics.json', metrics)
        print(json.dumps({'returncode': 0, 'origin': args.origin, 'steps': metrics['instruction_count'],
                          'cpu_seconds': metrics['total_cpu_seconds'], 'wall_seconds': metrics['wall_seconds']}), flush=True)
        return 0
    except BaseException:
        traceback.print_exc()
        metrics.update(returncode=1, wall_seconds=time.monotonic() - began, **usage())
        emit(out / 'metrics.json', metrics)
        return 1
    finally:
        if machine is not None: machine.close()

if __name__ == '__main__':
    raise SystemExit(main())
