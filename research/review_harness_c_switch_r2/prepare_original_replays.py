"""Retain previous review drivers with release and output path changes only."""
from pathlib import Path
import difflib,hashlib,json
ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
TMP='/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2'
rows=[]
for name in ('identity_args_r2.py','event_entry.py'):
    source=ROOT/'research/review_harness_c_switch'/name;a=source.read_text()
    b=a.replace("OUT = ROOT / 'research/review_harness_c_switch'",'OUT = Path('+repr(str(OUT))+')')
    b=b.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch',TMP)
    b=b.replace('tools/speedlab/harness_release\'','tools/speedlab/harness_release_r4\'')
    if name=='identity_args_r2.py':
        b=b.replace("'support.py', 'offline.sb',","'support.py', 'resume_identity.py', 'offline.sb',")
        b=b.replace("'backend_select.py', 'backend_launch.py'","'backend_select.py', 'backend_launch.py', 'input_trace.py', 'input_trace_strict.py'")
    else:b=b.replace("entry = OUT / 'identity/entry'","entry = OUT / 'entry'")
    target=OUT/('original_'+name);compile(b,str(target),'exec');target.write_text(b)
    rows.append({'source':str(source.relative_to(ROOT)),'copy':str(target.relative_to(ROOT)),
                 'source_sha256':hashlib.sha256(a.encode()).hexdigest(),'copy_sha256':hashlib.sha256(b.encode()).hexdigest(),
                 'diff':''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True)))})
(OUT/'evidence/original-replay-copies.json').write_text(json.dumps(rows,indent=2)+'\n')
