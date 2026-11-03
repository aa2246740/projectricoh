"""Record final review-script hashes and exact differences from reference scripts."""
from pathlib import Path
import difflib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, file_sha

rows=[]
diff=[]
for name in ('script-provenance.json','static-source-routing.json'):
    value=json.loads((OUT/name).read_text())
    entries=value['sources'] if isinstance(value,dict) else value
    for row in entries:
        source=ROOT/row['source']
        target=OUT/source.name
        if not target.exists() or target.suffix!='.py':continue
        assert file_sha(source)==row['sha256']
        rows.append(dict(source=row['source'],source_sha256=row['sha256'],
                         reviewed_file=target.name,reviewed_sha256=file_sha(target)))
        diff.extend(difflib.unified_diff(source.read_text().splitlines(True),target.read_text().splitlines(True),
                                       fromfile='reference/'+source.name,tofile='review/'+target.name))
(OUT/'review-script-changes.patch').write_text(''.join(diff))
save('review-script-changes.json',dict(status='PASS',sources=rows,
    final_scripts=[dict(file=p.name,sha256=file_sha(p)) for p in sorted(OUT.glob('*.py'))],
    scope='Test routing, write fence, whole-state checkpoints, added parameter cases and result reporting. No firmware compilation or edits.'))
initial=json.loads((OUT/'script-provenance.json').read_text())
save('first-matrix-command.json',dict(command=['/usr/bin/python3','-I','-B',
    'research/review_g120b/run_native.py','matrix','50mm'],returncode=0,
    output='matrix-50mm.log',result='native/matrix-50mm.json',
    initial_source_hashes=[row for row in initial if row['source'].endswith(('/run_native.py','/native_ux.py'))],
    scope='The foreground command completed with exit code zero. This initial run used the source scan and original functional CRC routing; the runtime origin guard was added for later runs.'))
print('PASS review source records',len(rows),flush=True)
