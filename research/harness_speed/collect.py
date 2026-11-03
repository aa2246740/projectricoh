"""Collect measured phases and profile samples without opening legacy sources."""
import collections
import json
from pathlib import Path
import pstats

HERE = Path(__file__).resolve().parent


def phase_name(event):
    name = event['name']
    if name == 'call':
        return 'interpreter_call' if event.get('steps') is not None else 'rpc_or_early_call'
    return name


def collect(folder):
    summary = json.loads((folder/'summary.json').read_text())
    phases = collections.defaultdict(lambda: dict(count=0, wall=0., cpu=0., steps=0))
    child_records = [json.loads(path.read_text()) for path in folder.glob('child_*.json')]
    for record in [summary]+child_records:
        for event in record.get('timings', ()):
            row = phases[phase_name(event)]
            row['count'] += 1
            row['wall'] += event['wall']
            row['cpu'] += event['cpu']
            row['steps'] += event.get('steps') or 0
    total_cpu = summary['cpu']+summary.get('child_cpu', 0.)
    first_cpu = sum(phases.get(k, {}).get('cpu', 0.) for k in ('boot', 'first_publish'))
    result = {k: summary.get(k) for k in ('name', 'side', 'mode', 'returncode', 'wall', 'cpu',
              'child_cpu', 'setup_wall', 'profile_window', 'fork_count', 'cache', 'max_rss',
              'runner_sha256', 'load_average')}
    result.update(total_cpu=total_cpu, phases=dict(phases), child_record_count=len(child_records),
                  child_failures=sum(bool(x['returncode']) for x in child_records),
                  first_prefix_cpu=first_cpu,
                  first_prefix_share=first_cpu/total_cpu if total_cpu else None)
    return result


def main():
    runs, profiles = [], {}
    for folder in sorted((HERE/'local').iterdir()):
        if not folder.is_dir() or not (folder/'summary.json').is_file():
            continue
        runs.append(collect(folder))
        profile = folder/'profile.bin'
        if profile.is_file():
            stats = pstats.Stats(str(profile))
            rows = []
            for (filename, line, name), (primitive, calls, own, cumulative, callers) in stats.stats.items():
                rows.append(dict(file=Path(filename).name, line=line, name=name,
                                 primitive_calls=primitive, calls=calls,
                                 own_seconds=own, cumulative_seconds=cumulative))
            rows.sort(key=lambda item:item['own_seconds'], reverse=True)
            profiles[folder.name] = dict(total_seconds=stats.total_tt,
                                         primitive_calls=stats.prim_calls,
                                         calls=stats.total_calls, hottest=rows[:30])
    result = dict(runs=runs, profiles=profiles)
    (HERE/'measurements.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(run_count=len(runs), profile_count=len(profiles))))


if __name__ == '__main__':
    main()
