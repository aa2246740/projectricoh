"""Seal all review files and verify the manifest with Apple's shasum."""
from pathlib import Path
import datetime
import json
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import OUT, file_sha, save

def files():
    result=sorted(x for x in OUT.rglob('*') if x.is_file() and x!=OUT/'SHA256SUMS')
    assert all(not x.is_symlink() and x.resolve().is_relative_to(OUT) for x in result)
    return result

def manifest():
    paths=files()
    (OUT/'SHA256SUMS').write_text(''.join(file_sha(p)+'  '+p.relative_to(OUT).as_posix()+'\n' for p in paths))
    return paths

def verify(paths):
    r=subprocess.run(['/usr/bin/shasum','-a','256','-c','SHA256SUMS'],cwd=OUT,text=True,capture_output=True)
    assert r.returncode==0,(r.returncode,r.stdout[-2000:],r.stderr)
    lines=r.stdout.splitlines()
    assert len(lines)==len(paths) and all(x.endswith(': OK') for x in lines)
    expected={p.relative_to(OUT).as_posix() for p in paths}
    listed={line.split('  ',1)[1] for line in (OUT/'SHA256SUMS').read_text().splitlines()}
    assert listed==expected=={p.relative_to(OUT).as_posix() for p in files()}
    return dict(checked=len(paths),all_ok=True,missing=[],extra=[],stderr=r.stderr)

def main():
    report=(OUT/'REVIEW.md').read_text()
    assert report.splitlines()[0]=='不可以上卡。'
    assert json.loads((OUT/'acceptance.json').read_text())['status']=='REVIEW_COMPLETED_WITH_BLOCKING_FINDINGS'
    integrity=json.loads((OUT/'input-integrity.json').read_text())
    assert integrity['unchanged'] and integrity['files']==25068
    for link in re.findall(r'\]\(([^)]+)\)',report):
        if link=='checksum-selfcheck.json':continue
        assert (OUT/link).exists(),('missing report evidence',link)
    preliminary=verify(manifest())
    save('checksum-selfcheck.json',dict(status='ALL_OK',
        preliminary=preliminary,final_file_count=preliminary['checked']+(not (OUT/'checksum-selfcheck.json').exists()),
        verifier='/usr/bin/shasum -a 256 -c SHA256SUMS',coverage='Every file below review_g118 except SHA256SUMS itself',
        final_pass='seal.py verifies the regenerated manifest again after writing this result and stops on any mismatch',
        input_files_unchanged=integrity['files'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    assert all((OUT/link).exists() for link in re.findall(r'\]\(([^)]+)\)',report))
    final=verify(manifest())
    assert final['checked']==json.loads((OUT/'checksum-selfcheck.json').read_text())['final_file_count']
    print('PASS SHA256SUMS',final['checked'],'/',final['checked'],'OK; complete file coverage; protected inputs',integrity['files'],'unchanged',flush=True)

if __name__=='__main__':main()
