"""Evaluate the unchanged M2c assertions against an explicit current freeze."""
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ACCEPT=HERE/'acceptance'
FAST=ROOT/'tools/gxr_emulator_fast/fix_r1'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    os.environ['GIT_OPTIONAL_LOCKS']='0'
    sys.path[:0]=[str(FAST),str(ACCEPT)]
    output=ACCEPT/'local'/a.suite
    historical_guard=json.loads((output/'final-input-guard.json').read_text())
    freeze=HERE/'runs/current-protected-inputs.json'
    current=json.loads(freeze.read_text())
    differences=[row['path'] for row in current['files'] if sha(ROOT/row['path'])!=row['sha256']]
    historical=[]
    for directory,relative in (('tools/gxr_emulator',True),('research/emulator_speed',False)):
        for line in (ROOT/directory/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1);path=(ROOT/directory/name) if relative else ROOT/name
            if sha(path)!=expected:historical.append(str(path.relative_to(ROOT)))
    old=json.loads((ROOT/'tools/gxr_emulator/local/protected-inputs.json').read_text())['files']
    old_ignore=next(row for row in old if row['path']=='.gitignore')
    raw=(ROOT/'.gitignore').read_bytes()
    guard=dict(historical_guard,unchanged_inputs=not differences,changed_inputs=differences,
               historical_inputs_unchanged=not historical,
               current_freeze=str(freeze.relative_to(ROOT)),current_freeze_sha256=sha(freeze),
               current_input_count=len(current['files']),historical_differences=historical)
    path=ACCEPT/'m2d_acceptance.py'
    spec=importlib.util.spec_from_file_location('current_m2c_assertions',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.OUT=output
    original=module.read
    module.read=lambda name:guard if name=='final-input-guard' else original(name)
    args=SimpleNamespace(cold='cold-suite-r1',stable='stable-suite-r1',card='cold-card-suite-r1',
                         regression='existing-checks-suite-r1',cumulative='m2b-suite-r1',file_series='suite-r1')
    result=module.m2c(args)
    result.update(passed=sum(bool(x) for x in result['checks'].values()),total=len(result['checks']),
                  scope='Current frozen inputs; historical M2c result remains unchanged.',guard=guard,
                  checker_sha256=sha(path),historical_checks=original('m2c-suite-r1')['checks'],
                  gitignore=dict(historical_prefix_matches=hashlib.sha256(raw[:old_ignore['size']]).hexdigest()==old_ignore['sha256'],
                                 appended_text=raw[old_ignore['size']:].decode(),
                                 provenance='Read from current .gitignore; matches independent-review fixed-inputs-audit.json. Uncommitted append author is not established.'))
    result['status']='PASS' if result['passed']==result['total'] else 'FAIL'
    target=ACCEPT/'runs'/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],passed=result['passed'],total=result['total'],changed=differences)))
    assert result['status']=='PASS'


if __name__=='__main__':main()
