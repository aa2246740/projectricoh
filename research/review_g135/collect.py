"""Collect the 81-group regression table from the runner result files (not from scheduler return codes alone)."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
CHECKS = WORK / 'local/checks'

def stem_of(args):
    script = args[args.index('research/review_g135/runner.py') + 1:]
    script = [a for a in script if a not in ('--crc-implementation', 'host', 'native')]
    path = Path(script[0])
    return path.parent.name, path.stem + '-' + '-'.join(script[1:]).replace('/', '_')

def main():
    plan = json.loads((WORK / 'plan.json').read_text())
    jobs = {j['name']: j for j in plan['jobs']}
    classes = json.loads((WORK / 'classification.json').read_text()) if (WORK / 'classification.json').exists() else {}
    state = {}
    for leg in ('schedule-state-v3.json',):
        if (WORK / leg).exists():
            s = json.loads((WORK / leg).read_text())
            state = dict(active=set(s['active']), remaining=set(s['remaining']))
    timebox = set()
    for leg in ('schedule-results-v3.json',):
        if (WORK / leg).exists():
            timebox |= {r['name'] for r in json.loads((WORK / leg).read_text()) if r.get('state') == 'TIMEBOX'}
    rows = []
    for row in plan['matrix']:
        job = jobs[row['name']]
        family, stem = stem_of(job['args'])
        result = CHECKS / family / f'result-{stem}.json'
        record = dict(row)
        if result.exists():
            data = json.loads(result.read_text())
            record.update(returncode=data['returncode'], seconds=data['seconds'], runner_sha256=data.get('runner_sha256'), result=str(result.relative_to(ROOT)))
            record['execution'] = 'FINISHED'
        elif row['name'] in state.get('active', ()):
            record.update(execution='RUNNING', returncode=None, seconds=None)
        elif row['name'] in timebox:
            record.update(execution='TIMEBOX', returncode=None, seconds=None)
        else:
            record.update(execution='NOT_RUN', returncode=None, seconds=None)
        if record.get('returncode'):
            tail = [a for a in job['args'][job['args'].index('research/review_g135/runner.py') + 1:] if a not in ('--crc-implementation', 'host', 'native')][1:]
            script_stem = stem.split('-', 1)[0]
            new_name = CHECKS / family / ('error-' + script_stem + '-' + '-'.join(tail).replace('/', '_') + '.json')
            old_name = CHECKS / family / ('error-' + script_stem + '.json')
            for candidate, exact in ((new_name, True), (old_name, False)):
                if candidate.exists():
                    e = json.loads(candidate.read_text())
                    last = e['location'][-1] if e.get('location') else {}
                    record['failure'] = dict(error=e.get('error'), message=str(e.get('message'))[:160], site=Path(last.get('file', '')).name + ':' + str(last.get('line')) + ':' + str(last.get('function')), exact_unit=exact)
                    break
        key = f"{row['family']}/{row['group']}"
        record['class'] = classes.get(key, {}).get('class')
        record['basis'] = classes.get(key, {}).get('basis')
        if record['execution'] == 'FINISHED':
            record['outcome'] = 'PASS' if record['returncode'] == 0 else (record['class'] or 'FAIL_UNCLASSIFIED')
        else:
            record['outcome'] = record['execution']
        rows.append(record)
    (WORK / 'regressions.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False) + '\n')
    counts = {}
    for r in rows:
        counts[r['outcome']] = counts.get(r['outcome'], 0) + 1
    print(json.dumps(counts, ensure_ascii=False))

if __name__ == '__main__':
    main()
