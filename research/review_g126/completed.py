"""Reuse only complete evidence freshly executed inside this review directory."""
from pathlib import Path
import json
import fcntl
from support import OUT, PIN

_locks=[]

def reuse(script, argv):
    unit=argv[argv.index('--unit')+1] if '--unit' in argv else '50mm'
    group=argv[0] if script=='ui_acceptance' else {
        'view_reentry':'view-reentry', 'other_users':'other-users', 'user_acceptance':'users',
        'project_boundary':'project-boundary','label_acceptance':'labels',
        'official_half':'official-half', 'reentry_all_keys':'reentry-all-keys',
        'lock_exits':'lock-exits-126',
    }.get(script)
    if not group:
        return False
    if script=='lock_exits' and any(flag in argv for flag in ('--actions','--record-tag')):
        return False
    folder=OUT/'local/suite-locks'
    folder.mkdir(parents=True,exist_ok=True)
    stream=(folder/(group+'-'+unit+'.lock')).open('a')
    fcntl.flock(stream,fcntl.LOCK_EX)
    _locks.append(stream)
    path=(OUT/'local'/('official-half-'+unit+'-with-hooks.json') if group=='official-half'
          else OUT/'evidence'/(group+'-'+unit+'.json'))
    if not path.exists():
        return False
    value=json.loads(path.read_text())
    expected=json.loads((OUT/'evidence/user-tool.json').read_text())['fixture_sha256'] if group in ('users','other-users') else PIN
    count={'transitions':42,'values':7,'view-reentry':70,'lock-exits-126':24,'reentry-all-keys':210}.get(group)
    ok=value.get('status','').startswith('PASS') and value.get('dat_sha256')==expected
    if count is not None:
        rows=value.get('cases',[])
        ok=ok and len(rows)==count and all(row['wait_status']==0 for row in rows)
    if ok:
        print('Already verified for final DAT:',group,unit,flush=True)
    return ok
