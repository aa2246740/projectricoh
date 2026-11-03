"""Copy replay scripts; restrict every producer to this review directory."""
from pathlib import Path
import difflib
import hashlib
import json

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SOURCE=ROOT/'research/g124_ui_v2'
NAMES='common support native_ux native_sequence ui_trace_scope runtime_guard run_cases safety_cases locked_cases lock_nested lock_cutpoints lock_exits official_half ui_test_support ui_acceptance view_reentry remaining_window user_acceptance tool_acceptance decode_error algorithm_check project_boundary label_acceptance static_audit binary_inventory compiled_tables memory_budget native_edges rpc_review codegen_safety build_package'.split()
patch=[]
for name in NAMES:
    src=SOURCE/(name+'.py'); original=src.read_text(); changed=original
    if name=='common':
        changed=changed.replace("OUT = ROOT / 'research/g124_ui_v2'", "OUT = ROOT / 'research/review_g124'")
        changed=changed.replace('(OUT, TREE, PACKAGE)', '(OUT,)')
    if name=='support':
        changed=changed.replace('PIN = hashlib.sha256(DAT.read_bytes()).hexdigest()', "PIN = 'ebf07faa3c5b8dcec411da7f7217fb58488adafb942045999bd2cdf7ce98f803'")
    (OUT/(name+'.py')).write_text(changed)
    patch.extend(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),
        fromfile=str(src.relative_to(ROOT)),tofile=str((OUT/(name+'.py')).relative_to(ROOT))))
(OUT/'replay-routing.patch').write_text(''.join(patch))
(OUT/'evidence/replay-provenance.json').write_text(json.dumps({
    name:dict(source=str((SOURCE/(name+'.py')).relative_to(ROOT)),
              source_sha256=hashlib.sha256((SOURCE/(name+'.py')).read_bytes()).hexdigest(),
              copied_sha256=hashlib.sha256((OUT/(name+'.py')).read_bytes()).hexdigest())
    for name in NAMES},indent=2)+'\n')
print('Copied',len(NAMES),'replay modules; production algorithms unchanged; fences tightened.')
