#!/usr/bin/env python3
"""Rebuild only the view from accepted model records, recording template edits."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import runtime as r
import preview


def main():
    r.setup()
    read=lambda name:json.loads((r.LOCAL/name).read_text())
    frames,metrics,inputs=read('frames.json'),read('metrics.json'),read('preview_inputs.json')
    key=str((r.HERE/'preview_template.html').relative_to(r.ROOT))
    old_hash=inputs['direct'][key];new_hash=r.sha(r.HERE/'preview_template.html')
    for path,digest in inputs['direct'].items():
        if path!=key:assert r.sha(r.ROOT/path)==digest
    preview.html(frames,metrics['scenes'],metrics['aggregates'])
    if old_hash!=new_hash:
        snapshot=r.LOCAL/'initial-preview-template.html'
        assert r.sha(snapshot)==old_hash
        inputs.setdefault('html_rebuild_history',[]).append(dict(old_template_sha256=old_hash,
            new_template_sha256=new_hash,old_template_snapshot=str(snapshot.relative_to(r.HERE)),
            reason='44px minimum width for short level buttons; image and metric calculations unchanged'))
        inputs['direct'][key]=new_hash
        r.dump(r.LOCAL/'preview_inputs.json',inputs)
    print(json.dumps(dict(rebuilt='local/preview.html',model_records=len(frames),template_changed=old_hash!=new_hash)))


if __name__=='__main__':main()
