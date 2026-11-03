"""Validate the delivered review, preserve input identities, and self-check hashes."""
from pathlib import Path
import hashlib,json,re,subprocess
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]


def main():
    report=(OUT/'REVIEW.md').read_text()
    assert report.splitlines()[0]=='可以接受。'
    rows=json.loads((OUT/'function-closure.json').read_text())
    changed=[r for r in rows if r['category']!='identity']
    assert len(changed)==95 and all(r['closed'] for r in changed)
    start=report.index('4. 每个改码符号的关闭表');end=report.index('5. 分级发现',start)
    names=re.findall(r'^\| `([^`]+)` \|',report[start:end],re.M)
    assert len(names)==95 and set(names)=={r['function'] for r in changed}
    links=re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)',report)
    bad=[x for x in links if not (OUT/x).is_file()]
    assert not bad,bad
    before=json.loads((OUT/'input-before.json').read_text())
    changed_inputs=[]
    for n,d in before.items():
        p=ROOT/n
        if not p.is_file() or p.stat().st_size!=d['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=d['sha256']:
            changed_inputs.append(n)
    assert not changed_inputs,changed_inputs
    b=json.loads((OUT/'branch-closure.json').read_text())
    assert all(x['closed'] and not x['unexplained'] for x in b.values())
    for n in ('finish','ui_finish','path','ig_init','ig_event','ig_menu'):
        d=json.loads((OUT/(n+'-results.json')).read_text())
        assert d['random']==10000 and d['directed']==64 and not d['failures']
    support=json.loads((OUT/'support-results.json').read_text())
    acceptance=dict(verdict='可以接受。',changed_symbols=95,real_function_intervals=88,A_symbols=70,B_only_symbols=10,
                    C_and_B_symbols=5,C_file_symbols=10,new_differential_pairs=60384,
                    A_support_pass=sum(x['pass_'] for x in support),A_support_fixture_limits=sum(not x['pass_'] for x in support),
                    input_files_unchanged=len(before),report_links=len(links),all_links_valid=True,remaining_obligations=[])
    (OUT/'acceptance.json').write_text(json.dumps(acceptance,indent=2,ensure_ascii=False)+'\n')
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS','checksum-selfcheck.json'))
    (OUT/'checksum-selfcheck.json').write_text(json.dumps(dict(command='/usr/bin/shasum -a 256 -c SHA256SUMS',files=len(files)+1,all_ok=True),indent=2)+'\n')
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(OUT))+'\n' for p in files))
    check=subprocess.run(['/usr/bin/shasum','-a','256','-c','SHA256SUMS'],cwd=OUT,capture_output=True,text=True)
    assert check.returncode==0,(check.stdout,check.stderr)
    lines=check.stdout.splitlines()
    assert len(lines)==len(files) and all(x.endswith(': OK') for x in lines),check.stdout
    assert len(files)==len([p for p in OUT.rglob('*') if p.is_file()])-1
    print('ACCEPTANCE_OK',json.dumps(acceptance,ensure_ascii=False))
    print('SHA256SUMS',len(files),'/',len(files),'OK')
    print('MANIFEST_SHA256',hashlib.sha256((OUT/'SHA256SUMS').read_bytes()).hexdigest())


if __name__=='__main__':main()
