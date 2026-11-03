"""Seal every review file and run standard SHA-256 checks twice."""
from pathlib import Path
import json
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import OUT,file_sha,save


def manifest():
    paths=sorted(path for path in OUT.rglob('*') if path.is_file() and path.name!='SHA256SUMS')
    (OUT/'SHA256SUMS').write_text(''.join(file_sha(path)+'  '+str(path.relative_to(OUT))+'\n' for path in paths))
    return len(paths)


def check(count):
    result=subprocess.run(['/usr/bin/shasum','-a','256','-c','SHA256SUMS'],cwd=OUT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    assert result.returncode==0,(result.returncode,result.stderr)
    lines=result.stdout.splitlines()
    assert len(lines)==count and all(line.endswith(': OK') for line in lines)
    return result.stdout


def main():
    assert json.loads((OUT/'verification.json').read_text())['status']=='PASS'
    (OUT/'sha-check.log').write_text('')
    save('checksum-selfcheck.json',dict(status='PASS',
        command='/usr/bin/shasum -a 256 -c SHA256SUMS',
        scope='Every regular file in this directory except SHA256SUMS itself.',
        sequence='Store the first standard check output, reseal that output too, then verify the final manifest again.'))
    count=manifest()
    result=check(count)
    (OUT/'sha-check.log').write_text('First verification before the final reseal.\n'+result)
    final_count=manifest()
    assert count==final_count
    check(final_count)
    print('PASS SHA256SUMS:',final_count,'/',final_count,'files OK; final manifest',file_sha(OUT/'SHA256SUMS'))


if __name__=='__main__':
    main()
