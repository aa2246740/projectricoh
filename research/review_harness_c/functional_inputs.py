"""Distinguish recorded concurrent ledger additions from execution-input changes."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha

enable()
before=json.loads((HERE/'local/inputs-before.json').read_text())
after=json.loads((HERE/'local/inputs-after.json').read_text())
ledger='research/speed_hillclimb/LEDGER.tsv'
expected=json.loads((ROOT/'research/speed_hillclimb/INPUTS.json').read_text())['files']
build=json.loads((ROOT/'tools/native_harness_c/local/ccore/build.json').read_text())
paths=set(expected)
paths.update(str(Path(name).relative_to(ROOT)) for name in build['sources'])
paths.add(str(Path(build['library']).relative_to(ROOT)))
paths.update(name for name in before if name.startswith('tools/speedlab/') and len(Path(name).parts)<=4)
current={name:sha(ROOT/name) for name in sorted(paths)}
changed=[name for name,value in current.items() if value!=before[name]]
functional_changes=[row for row in after['changed'] if row['path']!=ledger]
new_files=[name for row in after['membership'] for name in row['added']]
record=dict(original_end_check_passed=after['passed'],original_end_check_changes=after['changed'],
    original_registered_files=after['count'],registered_files_unchanged=after['count']-len(after['changed']),
    current_execution_inputs=current,current_execution_input_count=len(current),current_execution_inputs_unchanged=not changed,
    changed_execution_inputs=changed,other_existing_input_changes=functional_changes,
    concurrent_new_files=new_files,concurrent_new_file_count=len(new_files),
    ledger_is_not_an_execution_input=ledger not in expected,
    scope='only the originally frozen C backend, Python reference, compiler cache and reviewed batch runtime; new versions are excluded')
emit(HERE/'local/functional-inputs.json',record)
assert not changed and not functional_changes and ledger not in expected
assert build['sha256']=='15f9b4e4cc28ff727d56f269ef57f7b938bb115485cd528996761158922b072f'
print(json.dumps(dict(current_execution_input_count=len(current),unchanged=True,
    registered_files_unchanged=record['registered_files_unchanged'],concurrent_new_file_count=len(new_files))),flush=True)
