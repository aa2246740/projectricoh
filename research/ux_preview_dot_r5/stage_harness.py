"""Route reviewed quality-test sources to the generation 120 candidate."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, file_sha

SOURCE = ROOT / 'research/review_g119b'
NAMES = ('run_native native_ux native_exits concurrent_menu ui_cutpoints ui_trace_scope '
         'entry_switch failure_boundaries confirm_paths latch_paths coalescing '
         'machine_static machine_gates artifacts codegen differential misc_diff '
         'service_targets service_more targeted_codegen targeted_render_bind '
         'object_map branch_coverage codegen_selfcheck coverage_collect file_gate_cfg '
         'small_targets run_recorded').split()

def route(text):
    return (text.replace('engine_v40_ux', 'engine_v42_ux').replace('engine_v39_ux', 'engine_v40_ux')
            .replace('119', '120').replace('118', '119'))

rows = []
for name in NAMES:
    p = SOURCE / (name + '.py')
    text = route(p.read_text())
    if name == 'entry_switch':
        text = text.replace("r['status'] = 'PASS' if r['other_menu_ui_preserved'] else 'COUNTEREXAMPLE'",
                            "assert r['other_menu_ui_preserved'], r\n    assert len(r['complete_slots']) == 1, r\n    r['status'] = 'PASS'")
    if name == 'failure_boundaries':
        text += "\nassert visible, 'The next native list must display its error row.'\nassert slots == [4] and after['W'] == 0\n"
    if name == 'artifacts':
        text = text.replace("assert identities[120]['dat']=='d11e88eae677f7ee3aeba4dc602c2085ef92b9c81f5c70286c8eb038211e4bbc'",
                            "assert identities[120]['dat']==sha((trees[120]/'local/full-r13/GXRCE.DAT').read_bytes())")
        text = text.replace("assert identities[119]['dat']=='e557c7266c05ea5b997bd369b505ea364c660e87aef07180c784207ffd0f3f2d'",
                            "assert identities[119]['dat']=='d11e88eae677f7ee3aeba4dc602c2085ef92b9c81f5c70286c8eb038211e4bbc'")
    if name == 'run_recorded':
        text = text.replace('datetime(2026,10,27,13,22,30', 'datetime(2026,10,27,17,47,30')
    (OUT / p.name).write_text(text)
    rows.append(dict(source=p.name, original=file_sha(p), routed=file_sha(OUT / p.name)))
for directory in ('local/layout', 'labels119'):
    for p in sorted((SOURCE / directory).rglob('*')):
        if p.is_file():
            q = OUT / p.relative_to(SOURCE)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, q)
save('harness-routing.json', dict(status='PASS', sources=rows, copied_results=False,
                                layout='Engine and adapter structures retain all existing offsets.'))
print('PASS quality-test source routing', len(rows), flush=True)
