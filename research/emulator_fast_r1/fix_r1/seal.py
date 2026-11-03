"""Freeze or verify the candidate, current inputs and untouched legacy entry."""
import argparse,datetime,hashlib,json,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FAST=ROOT/'tools/gxr_emulator_fast/fix_r1'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--verify',type=Path);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    build=json.loads((FAST/'build/native-build.json').read_text())
    assert all(sha(FAST/name)==digest for name,digest in build['source_hashes'].items())
    inputs=json.loads((HERE/'runs/current-protected-inputs.json').read_text())['files']
    environment=json.loads((HERE/'runs/restart-environment.json').read_text())
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in inputs)
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in environment['legacy_entry_files'])
    files=[p for p in FAST.iterdir() if p.is_file() and p.suffix in ('.py','.c','.h','.inc','.json')]
    files += [p for p in (FAST/'build').iterdir() if p.is_file() and
              (p.name=='libgxr_m32r.dylib' or p.name.startswith('_gxr_wire') and p.suffix=='.so')]
    rows=[dict(path=str(p.relative_to(ROOT)),size=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    if a.verify:assert rows==json.loads(a.verify.read_text())['files']
    result=dict(status='PASS',when=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                files=rows,build=build,current_inputs=len(inputs),legacy_entry_files=len(environment['legacy_entry_files']),
                library_sha256=build['library_sha256'],extension_sha256=build['extension_sha256'],load=os.getloadavg())
    target=HERE/'runs'/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','build')}))


if __name__=='__main__':main()
