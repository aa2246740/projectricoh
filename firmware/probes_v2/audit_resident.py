#!/usr/bin/env python3
"""Capture targeted, read-only source evidence from the parallel resident."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WINDOWS = {
    'services.c': [
        ('buffer_lease_guard', 'if(!rv_range(r,q->args[1],q->args[10],bytes)', 3, 5),
        ('lease_inspect_target', 's->leases[i].token!=q->args[1]', 3, 11),
        ('lease_free_result', 'rv_native_free(x);', 2, 3),
        ('snapshot_outputs', 'case RV_UNIT:', 0, 10),
        ('settings_snapshot', 'if(op==1){s->settings=address;', 2, 4),
        ('storage_eof_limit', 'a[7]>s->file_limit[i]-s->file_bytes[i]', 2, 6),
        ('events_header', 'case RV_EVENTS:', 0, 10),
        ('epoch_current_guard', 'if(!current(r,q))', 2, 6),
        ('reply_epilogue', 'p->status=result;', 2, 2),
    ],
    'loader.c': [('bootstrap_init_payload', 'q.args[10]=address+offsetof(RvSession,entries)', 2, 18)],
    'resident.c': [('entry_epochs', 'int32_t rv_engine(', 0, 17)],
    'resident.h': [('ui_capability', 'CAP_FILE_WRITE=', 0, 2),
                   ('loader_allocation', 'RV_IMAGE_BYTES=', 1, 3)],
}


def main():
    spec = importlib.util.spec_from_file_location('pv_support', HERE/'support.py')
    s = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s)
    s.preflight()
    out = s.LOCAL/'integration'
    out.mkdir(exist_ok=True)
    files = []
    for name, windows in WINDOWS.items():
        path = ROOT/'firmware/resident_impl'/name
        raw = path.read_bytes()
        lines = raw.decode().splitlines()
        captured = []
        for label, needle, before, after in windows:
            matches = [i for i, line in enumerate(lines) if needle in line]
            blocks = []
            for i in matches:
                start, end = max(0, i-before), min(len(lines), i+after+1)
                blocks.append(dict(first_line=start+1, last_line=end,
                                   text='\n'.join(lines[start:end])))
            captured.append(dict(label=label, found=bool(matches), blocks=blocks))
        files.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(raw).hexdigest(), windows=captured))
    result = dict(captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  evidence='static shared-source snapshot only; not resident execution', files=files)
    old_header = ROOT/'firmware/card_container/gxrce.h'
    raw = old_header.read_bytes()
    result['legacy_container_limits'] = dict(path=str(old_header.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),
        lines=[dict(line=i+1,text=line) for i,line in enumerate(raw.decode().splitlines()) if 'GXRCE_MAX_FILE' in line or 'GXRCE_MAX_BSS' in line])
    (out/'snapshot.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('Captured '+str(sum(len(f['windows']) for f in files))+' targeted windows; resident execution not tested')


if __name__ == '__main__':
    main()
