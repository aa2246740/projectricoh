"""Stale source-directory layout files (what MATERIALS points at) against the layout rebuilt for gen 135."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
new_dir = WORK / 'local/checks/review_g126/local/layout'
out = {}
for family in ('review_g124', 'review_g126'):
    old_dir = ROOT / 'research' / family / 'local/layout'
    entry = {}
    for name in ('layout.json', 'current-adapter-layout.json'):
        old, new = json.loads((old_dir / name).read_text()), json.loads((new_dir / name).read_text())
        entry[name] = dict(changed={k: [old.get(k), new.get(k)] for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)},
                           total_fields=len(set(old) | set(new)))
        entry[name]['changed_count'] = len(entry[name]['changed'])
    out[family] = entry
adapter_impl = json.loads((ROOT / 'research/g135_v37/adapter-layout.json').read_text())
rebuilt = json.loads((new_dir / 'current-adapter-layout.json').read_text())
# the implementer's adapter-layout.json stores the ui.* offsets relative to the 'ui' base; the rebuilt file stores them from the adapter origin
shared = {k: (adapter_impl['ui'] + adapter_impl[k] if k.startswith('ui.') and k in rebuilt and k != 'ui.nav' else adapter_impl[k]) == rebuilt[k]
          for k in adapter_impl if k in rebuilt}
out['implementer_adapter_layout_equals_rebuilt_on_shared_keys'] = all(shared.values())
out['implementer_adapter_layout_unequal_keys'] = [k for k, v in shared.items() if not v]
out['implementer_adapter_layout_keys_missing_in_rebuilt'] = [k for k in adapter_impl if k not in rebuilt]
out['core_layout_equals_implementer'] = (new_dir / 'layout.json').read_bytes() == (ROOT / 'research/g135_v37/local/checks/review_g126/local/layout/layout.json').read_bytes()
(WORK / 'layout-diff.json').write_text(json.dumps(out, indent=1) + '\n')
print({f: {n: v['changed_count'] for n, v in e.items()} for f, e in out.items() if f.startswith('review')}, out['implementer_adapter_layout_equals_rebuilt_on_shared_keys'], out['implementer_adapter_layout_keys_missing_in_rebuilt'], out['core_layout_equals_implementer'])
