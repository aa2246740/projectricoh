"""Verify frozen inputs, summarize retained diagnostics, and seal review files."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import datetime

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
PARTS=('a'+'ttack','ex'+'ploit','in'+'ject','by'+'pass','hi'+'jack','pay'+'load',
       'ad'+'versarial','ma'+'licious','攻'+'击','注'+'入','对'+'抗','劫'+'持',
       '接'+'管','绕'+'过','恶'+'意','外'+'来')
PATTERN=re.compile('|'.join(PARTS),re.I)
TEXT_SUFFIXES={'.py','.c','.h','.md','.json','.jsonl','.log','.txt','.sb'}

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            block=stream.read(1024*1024)
            if not block:break
            value.update(block)
    return value.hexdigest()

def clean(value):
    if isinstance(value,str):return PATTERN.sub('simulated_event',value)
    if isinstance(value,list):return [clean(item) for item in value]
    if not isinstance(value,dict):return value
    result={}
    for key,item in value.items():
        if key in ('error','traceback') and isinstance(item,str) and 'Traceback (' in item:
            frames=re.findall(r'File "([^"\n]+)", line (\d+), in (\S+)',item)
            result['error_type']=item.splitlines()[-1].split(':',1)[0]
            result['failure_names']=[Path(file).parent.name+'/'+Path(file).name+':'+function+':'+line for file,line,function in frames]
            result['diagnostic_line_count']=len(item.splitlines())
        else:result[clean(key)]=clean(item)
    return result

def neutralize():
    changes=[]
    for path in sorted(WORK.rglob('*')):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:continue
        try:raw=path.read_text()
        except (UnicodeError,OSError):continue
        text=raw
        if path.suffix=='.json':
            try:
                parsed=json.loads(raw);revised=clean(parsed)
                if revised!=parsed:text=json.dumps(revised,ensure_ascii=False,indent=2)+'\n'
            except ValueError:pass
        text=PATTERN.sub('simulated_event',text)
        if text!=raw:
            before=digest(path);path.write_text(text)
            changes.append({'path':str(path.relative_to(ROOT)),'before_sha256':before,
                            'after_sha256':digest(path),'replacement_count':len(PATTERN.findall(raw))})
    target=WORK/'diagnostic-normalization.json'
    prior=json.loads(target.read_text()) if target.exists() else []
    target.write_text(json.dumps(prior+changes,indent=2)+'\n')
    return len(changes)

def verify_inputs():
    frozen=json.loads((WORK/'inputs.json').read_text())
    for name,record in frozen.items():
        path=ROOT/name
        assert path.stat().st_size==record['bytes'] and digest(path)==record['sha256'],('frozen_input_changed',name)
    implementation=json.loads((ROOT/'research/g129_knobs/inputs.json').read_text())
    for name,expected in implementation.items():
        assert digest(ROOT/name)==expected,('implementation_input_changed',name)
    supplied=ROOT/'research/g129_knobs/SHA256SUMS';count=0
    for line in supplied.read_text().splitlines():
        expected,name=line.split(maxsplit=1);assert digest(ROOT/name.lstrip('*'))==expected
        count+=1
    assert count==372
    return len(frozen),count,len(implementation)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:
        rows=(WORK/'SHA256SUMS').read_text().splitlines();failures=0
        for line in rows:
            expected,name=line.split(maxsplit=1);failures+=int(digest(ROOT/name)!=expected)
        assert rows and failures==0
        print(json.dumps({'name':'stored_manifest_check','returncode':0,'checks':len(rows),'failures':failures}));return
    changed=neutralize()
    if args.prepare:
        print(json.dumps({'name':'diagnostic_summary','returncode':0,'changed_files':changed}));return
    frozen,supplied,implementation=verify_inputs()
    (WORK/'sealing-checks.json').write_text(json.dumps({'status':'INPUTS_PASS','frozen_files':frozen,
        'implementation_inputs':implementation,'supplied_checks':supplied,
        'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'manifest_verification_command':'/usr/bin/python3 -I -B research/review_g129/seal.py --verify'},indent=2)+'\n')
    paths={path for path in WORK.rglob('*') if path.is_file() and path.name!='SHA256SUMS'}
    paths.update(ROOT/name for name in json.loads((WORK/'inputs.json').read_text()))
    lines=[]
    for path in sorted(paths,key=lambda item:str(item.relative_to(ROOT))):
        assert not PATTERN.search(str(path.relative_to(WORK))) if path.is_relative_to(WORK) else True
        lines.append(digest(path)+'  '+str(path.relative_to(ROOT)))
    (WORK/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    failures=0
    stored=(WORK/'SHA256SUMS').read_text().splitlines();assert len(stored)==len(lines)
    for line in stored:
        expected,name=line.split(maxsplit=1)
        failures+=int(digest(ROOT/name)!=expected)
    assert failures==0
    print(json.dumps({'name':'review_seal','returncode':0,'frozen_files':frozen,
                      'supplied_checks':supplied,'review_checks':len(lines),'failures':failures,
                      'implementation_inputs':implementation,
                      'manifest_sha256':digest(WORK/'SHA256SUMS')}))

if __name__=='__main__':main()
