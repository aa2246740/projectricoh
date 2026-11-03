from pathlib import Path
import hashlib
import dis
import json
import runpy
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'


def functions(code, prefix=''):
    result = {}
    for item in code.co_consts:
        if isinstance(item, types.CodeType):
            name = prefix + item.co_name
            result[name] = item
            result.update(functions(item, name + '/'))
    return result


def constants(code):
    return [constants(value) if isinstance(value, types.CodeType) else value for value in code.co_consts]


rows = []
for filename in ['ui_acceptance.py', 'label_acceptance.py', 'project_boundary.py', 'safety_cases.py']:
    paths = [ROOT / ('research/review_g' + str(family)) / filename for family in [124, 126]]
    code = [runpy._get_code_from_file('review_contract', str(path))[0] for path in paths]
    left, right = map(functions, code)
    comparisons = []
    for name in sorted(left.keys() & right.keys()):
        a, b = left[name], right[name]
        comparisons.append({'function': name, 'same_operations': a.co_code == b.co_code, 'same_names': a.co_names == b.co_names, 'same_constants': constants(a) == constants(b)})
    rows.append({'file': filename, 'sha256': [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths], 'functions': comparisons, 'left_only': sorted(left.keys() - right.keys()), 'right_only': sorted(right.keys() - left.keys())})
(OUT / 'evidence/family-contracts.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps([{'file': row['file'], 'functions': len(row['functions']), 'different': [item['function'] for item in row['functions'] if not all(item[key] for key in ['same_operations', 'same_names', 'same_constants'])]} for row in rows]))
paths = [ROOT / 'research/review_g126/ui_acceptance.py', ROOT / 'research/review_g135/legacy/ui_acceptance_g135.py']
groups = [functions(runpy._get_code_from_file('review_contract', str(path))[0]) for path in paths]
comparisons = []
for name in sorted(groups[0].keys() & groups[1].keys()):
    pair = [group[name] for group in groups]
    counts = [sum(instruction.opname == 'LOAD_ASSERTION_ERROR' for instruction in dis.get_instructions(code)) for code in pair]
    calls = [{word: code.co_names.count(word) for word in ['press', 'match', 'rpc_log', 'writes']} for code in pair]
    comparisons.append({'function': name, 'assertion_counts': counts, 'observed_method_names': calls})
(OUT / 'evidence/port-contracts.json').write_text(json.dumps(comparisons, indent=2) + '\n')
print(json.dumps({'port_function_count': len(comparisons), 'fewer_assertions': [row['function'] for row in comparisons if row['assertion_counts'][1] < row['assertion_counts'][0]]}))
