"""Foreground, sequential, recorded replay queue. No build or device action."""
from pathlib import Path
import subprocess
import sys

O = Path(__file__).resolve().parent
R = O.parents[1]
lane = sys.argv[1]
unit = sys.argv[2] if len(sys.argv) > 2 else None
jobs = []

if lane == 'native':
    # The first matrix-50mm and ah-28mm runs were started separately.
    if unit != '50mm':
        jobs.append(('matrix-' + unit, 'run_native.py', 'matrix', unit))
    if unit != '28mm':
        jobs.append(('ah-' + unit, 'run_native.py', 'ah', unit))
    jobs.append(('persistent-' + unit, 'run_native.py', 'persistent', unit))
    jobs.append(('exits-' + unit, 'run_native.py', 'exits', unit))
    for at in (1, 16, 140):
        if unit == '50mm' and at == 1:
            continue
        jobs.append(('foreign-' + unit + '-at' + str(at), 'adversarial.py', 'foreign', unit, '--at', str(at), '--reopen-fn2'))
    for group in ('recovery', 'fallback', 'nested'):
        jobs.append((group + '-' + unit, 'adversarial.py', group, unit))
    for point in ('redraw', 'cache'):
        jobs.append(('ui-' + point + '-' + unit, 'ui_cutpoints.py', point, unit))
    for entry in ('fn2', 'ok', 'adj'):
        if (unit, entry) in (('50mm', 'fn2'), ('50mm', 'ok'), ('28mm', 'fn2')):
            continue
        jobs.append(('entry-' + entry + '-' + unit, 'entry_takeover.py', unit, entry))
elif lane == 'B1':
    for name in ('es_range.constprop.0', 'identity.constprop.0', 'same.constprop.0', 'ui_prepare.constprop.0', 'ingress',
                 'es_session', 'finish', 'ui_finish', 'write_word', 'preview_cached', 'ig_panel_open', 'ig_panel_event', 'core_call', 'rv_call'):
        jobs.append(('B-' + name.replace('.', '-').replace('_', '-'), 'misc_diff.py', name, '10000'))
elif lane == 'B2':
    for name in ('list_bind', 'panel_render', 'ig_menu', 'ig_event', 'ig_apply'):
        jobs.append(('B-' + name.replace('_', '-'), 'differential.py', name, '10000'))
else:
    raise ValueError(lane)

failed = []
for label, script, *args in jobs:
    print('BEGIN', label, flush=True)
    rc = subprocess.call(['/usr/bin/python3', '-I', '-B', str(O / 'run_recorded.py'), label,
                          '/usr/bin/python3', '-I', '-B', str(O / script), *args], cwd=R)
    print('END', label, 'exit', rc, flush=True)
    if rc:
        failed.append((label, rc))
print('QUEUE FINISHED', lane, unit, 'failures', failed, flush=True)
raise SystemExit(bool(failed))
