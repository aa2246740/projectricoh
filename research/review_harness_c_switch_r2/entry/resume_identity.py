"""Current test code, complete queue and actual runtime input identities."""
import hashlib,json,os
from pathlib import Path
from support import ROOT,HERE,sha

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def explicit_files(queue):
    result={}
    def visit(value):
        if isinstance(value,dict):
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,str):
            path=Path(value) if os.path.isabs(value) else ROOT/value
            if path.is_file():result[str(path.absolute())]=sha(path)
    visit(queue);return result

def selection(queue,slots):
    # Values stay out of the receipt; the fingerprint still detects environment changes.
    env={k:v for k,v in os.environ.items() if k not in ('_','SHLVL')}
    return {'schema':3,'queue_sha256':digest(queue),'slots':slots,'explicit_files':explicit_files(queue),
            'environment_sha256':digest(env)}

def probe_path(name):
    path=Path(name)
    if path.is_file():kind='file'
    elif path.is_dir():kind='directory'
    elif path.exists():kind='other'
    else:kind='absent'
    return {'kind':kind,'resolved':os.path.realpath(name)}

def collect_inputs(folder):
    folder=Path(folder);records=sorted(folder.glob('process-*.json'))
    if not records:raise RuntimeError('runtime input identity missing; run again with a new name')
    files={};probes={}
    for path in records:
        record=json.loads(path.read_text())
        if not record.get('complete') or record.get('drift'):raise RuntimeError('runtime inputs changed during execution')
        for name,value in record['files'].items():
            if name in files and files[name]!=value:raise RuntimeError('runtime input identity differs across processes')
            files[name]=value
        for name,value in record.get('import_probes',{}).items():
            if name in probes and probes[name]!=value:raise RuntimeError('import resolution differs across processes')
            probes[name]=value
    return {'schema':3,'files':files,'import_probes':probes,'records':{p.name:sha(p) for p in records}}

def verify_inputs(expected,folder):
    if not expected or expected.get('schema')!=3:raise RuntimeError('runtime input identity absent; use a new run name')
    folder=Path(folder)
    records={p.name:sha(p) for p in sorted(folder.glob('process-*.json'))}
    if records!=expected['records']:raise RuntimeError('runtime input receipts differ')
    for name,value in expected['files'].items():
        path=Path(name)
        if not path.is_file() or os.path.realpath(name)!=value['resolved'] or sha(path)!=value['sha256']:
            raise RuntimeError('runtime input or dependency identity differs: '+name)
    for name,value in expected['import_probes'].items():
        if probe_path(name)!=value:raise RuntimeError('import resolution identity differs: '+name)
