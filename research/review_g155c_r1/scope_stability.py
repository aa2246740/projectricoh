"""Separate an external append-only decision log from frozen product inputs."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

before=json.loads((C.HERE/'evidence/inputs-before.json').read_text())
changed=[]
append=None
unchanged=0
for row in before['files']:
    path=C.ROOT/row['path']
    raw=path.read_bytes()
    if len(raw)==row['bytes'] and C.digest(raw)==row['sha256']:
        unchanged+=1
        continue
    if row['path']=='decisions.tsv' and len(raw)>row['bytes'] and C.digest(raw[:row['bytes']])==row['sha256']:
        copy=C.HERE/'local/decisions-after.tsv'
        assert not copy.exists()
        copy.write_bytes(raw)
        append=dict(path='decisions.tsv',before_bytes=row['bytes'],before_sha256=row['sha256'],
                    after_bytes=len(raw),after_sha256=C.digest(raw),appended_bytes=len(raw)-row['bytes'],
                    original_prefix_equal=True,sealed_copy=C.file_info(copy),
                    classification='External decision log; not a DAT, engine, body, tool, or test input.')
    else:
        changed.append(row['path'])
assert not changed,changed
C.save('inputs-after-scoped',dict(status='PASS',checked_files=len(before['files']),unchanged_files=unchanged,
                                 product_or_tool_mismatches=changed,external_append=append,
                                 earlier_broad_check='inputs-after.json retains the real whole-set mismatch. It is not relabeled.',
                                 SHA256SUMS_exclusion='Live decisions.tsv is excluded; its sealed copy and both hashes are retained.'))
