"""Seal/verify this review only. Never updates candidate metadata."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c


def required():
    scope=json.loads((c.LOCAL/'scope-check.json').read_text())
    assert scope['files']==259944 and not scope['changes'] and scope['tracked_equal']
    assert (c.HERE/'REPORT.md').read_text().splitlines()[0]=='可以刷机'
    assert (c.HERE/'.gitignore').read_text()=='/local/\n'
    for name in ('artifacts.json','data.json','cold-machine.json','machine-reuse.json','machine-symbols.json','additional-flows.json'):
        assert json.loads((c.LOCAL/name).read_text())['status'].startswith('PASS'),name
    assert json.loads((c.LOCAL/'host-suite.json').read_text())['runs']==146
    assert json.loads((c.LOCAL/'additional-flows.json').read_text())['runs']==14
    assert c.sha(c.PACKAGE/'SD_ROOT/ilaunch3')=='24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72'
    assert c.sha(c.PACKAGE/'SD_ROOT/GXRCE.DAT')=='6cb63aa47c18086f5ade681ffe4dc97378394ff7a65c0688d19b3880d804c707'


def files():
    result=[]
    for p in sorted(c.HERE.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file() and p!=c.HERE/'SHA256SUMS':result.append(p)
    return result


def seal():
    required()
    c.save('delivery.json',dict(status='PASS_REVIEW_ONLY',verdict='可以刷机',product_host_programs=160,
           protected_files=259944,decisions_excluded=True,camera_acceptance=False,candidate_rebuilt=False,
           new_blocking_findings=0,retained_limits=['F02','unreadable CTL OFF','unobserved late DAT','native/hardware acceptance']))
    (c.HERE/'SHA256SUMS').write_text(''.join(c.sha(p)+'  '+str(p.relative_to(c.HERE))+'\n' for p in files()))
    verify()


def verify():
    required();record={}
    for line in (c.HERE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);path=c.HERE/name
        path.resolve().relative_to(c.HERE)
        assert name not in record and len(digest)==64 and c.sha(path)==digest,name
        record[name]=digest
    assert set(record)=={str(p.relative_to(c.HERE)) for p in files()}
    print('PASS review SHA256SUMS:',len(record),'files; candidate identities verified; full input snapshot result unchanged')


if __name__=='__main__':{'seal':seal,'verify':verify}[sys.argv[1]]()
