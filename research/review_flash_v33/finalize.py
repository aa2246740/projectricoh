"""Seal or verify this review only. No firmware build, package or camera actions."""
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review as c

PHASES=('first-frame','upgrades','regressions','faults','guard')

def audit_host():
    summary={};total=0;counterexamples=[]
    for phase in PHASES:
        path=c.LOCAL/('host-'+phase+'.json');d=json.loads(path.read_text());assert d['runs']==len(d['cases'])
        count=0
        for case in d['cases']:
            log=c.HERE/case['log'];text=log.read_text();last=text.rstrip().splitlines()[-1]
            assert last.startswith('OK '),str(log)
            observed=int(re.search(r'assertions=(\d+)',last)[1]);assert observed==case['assertions']
            count+=observed
            if phase=='guard':
                assert 'one_native_error=1' in text
                bad='GUARD_PERSISTED' in text
                case['safety_outcome']='COUNTEREXAMPLE' if bad else 'ZERO_WRITES_CONTROL'
                if bad:
                    assert 'active_generation=111 selected_source=1' in text
                    assert 'op=2 raw=-1' in text and 'writes=3 renames=1' in text
                    counterexamples.append(case)
                else:assert 'writes=0 renames=0' in text
        assert count==d['assertions']
        summary[phase]=dict(runs=d['runs'],assertions=count);total+=d['runs']
        if phase=='guard':
            d['status']='COUNTEREXAMPLES_REPRODUCED'
            d['counterexamples']=len(counterexamples)
            d['zero_write_controls']=d['runs']-len(counterexamples)
            c.write(path.name,d)
    assert total==2132 and len(counterexamples)==8
    return dict(runs=total,phases=summary,counterexamples=counterexamples)

def validate_report(allow_future_sums=False):
    report=c.HERE/'REPORT.md';text=report.read_text()
    assert text.splitlines()[0]=='不可以刷机'
    links=re.findall(r'(?<!!)\[[^]]*\]\(([^)]+)\)',text)
    for link in links:
        assert '://' not in link
        p=(c.HERE/link.split('#')[0]).resolve()
        assert p.is_file() or (allow_future_sums and p==c.HERE/'SHA256SUMS'),link
    return links

def seal():
    c.unchanged()
    host=audit_host()
    for name,expected in [('image','PASS'),('data','PASS'),('scope-summary','PASS'),
        ('bounded-dispatch','PASS'),('recovery','PASS_STATIC_BOUNDED'),('image-faults','PASS'),
        ('resident-host','PASS'),('irq','PASS'),('constructor-machine','PASS'),
        ('machine-ownership','PASS'),('stack','PASS_BOUNDED_MODEL'),('builder-count-audit','PASS_RECORDED_COUNT_ONLY')]:
        assert json.loads((c.LOCAL/(name+'.json')).read_text())['status']==expected,name
    report=(c.HERE/'REPORT.md').read_text();links=validate_report(allow_future_sums=True)
    assert (c.HERE/'.gitignore').read_text()=='/local/\n'
    assert '/local/' in c.run(['git','check-ignore','-v',c.LOCAL/'probe'])
    misplaced=[]
    for p in c.HERE.rglob('*'):
        assert not p.is_symlink()
        if not p.is_file():continue
        if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p))
        if p.suffix in ('.bin','.DAT','.elf','.o','.su','.log','.disasm','.fixture') and c.LOCAL not in p.parents:misplaced.append(str(p))
    assert not misplaced
    binaries={str(p.relative_to(c.HERE)):c.digest(p) for folder in ('host','resident-host') for p in (c.LOCAL/folder).iterdir() if p.is_file() and p.suffix==''}
    c.write('findings.json',dict(verdict='不可以刷机',approval=False,date='2026-10-25',
        package='firmware/image_v33/local/package_final/SD_ROOT',
        image_sha256='7f01e7535a0c3ebe84bf2d7a060590b24b19f0e1065afc7fe1762973f3f08546',
        dat_sha256='7fc825755406c8dccd49d49277098afedd478ec45260d53893bf0c55d0ab6e7b',
        findings=[dict(id='R33-01',severity='P2',blocks_package=True,
            title='A single native DAT open failure permits saving despite an already rejected old DAT',
            code=['firmware/resident_v33/acceptance/containers/product/adapter.c:287',
                  'firmware/resident_v33/acceptance/containers/product/adapter.c:310',
                  'firmware/resident_v33/acceptance/containers/product/adapter.c:339',
                  'firmware/resident_v33/acceptance/engine_services/services.c:117'],
            reproductions=host['counterexamples'],native_M32R_execution=False,physical_persistence=False)],
        new_P0_or_P1_found=False,accepted=['F02 persistent IROM open ambiguity','ISO100 row14 curve bypass',
            'R7-03 unclosed menu preserves prior full memory','incomplete stack model','unit swap disables session'],
        raw_host_runs=host,compiled_host_binaries=binaries,camera_or_card_accessed=False,
        candidate_rebuilt=False,candidate_repackaged=False,subagents_used=False))
    c.write('delivery.json',dict(status='PASS_REVIEW_DELIVERY_NOT_FIRMWARE_APPROVAL',
        verdict='不可以刷机',protected_inputs=33201,report_links_verified=len(links),
        ignored_local=True,derived_files_outside_local=misplaced,report_sha256=hashlib.sha256(report.encode()).hexdigest(),
        limits='Offline artifact bytes, compiled host C and bounded instruction models. No camera/flash/runtime recovery proof.'))
    c.sums()
    verify()

def verify():
    sums=c.HERE/'SHA256SUMS';seen=set()
    for line in sums.read_text().splitlines():
        wanted,name=line.split('  ',1);p=(c.HERE/name).resolve()
        assert p.is_relative_to(c.HERE) and name not in seen;seen.add(name)
        assert c.digest(p)==wanted,name
    actual={str(p.relative_to(c.HERE)) for p in c.HERE.rglob('*') if p.is_file() and p!=sums}
    assert actual==seen,(actual-seen,seen-actual)
    validate_report()
    d=json.loads((c.LOCAL/'inputs-final.json').read_text());assert not d['changes'] and d['tracked_status_unchanged']
    finding=json.loads((c.LOCAL/'findings.json').read_text())
    assert finding['approval'] is False and finding['findings'][0]['blocks_package']
    print('VERIFIED',len(seen),'SHA256SUMS entries; 33201 frozen inputs unchanged; NOT APPROVED')

if __name__=='__main__':{'seal':seal,'verify':verify}[sys.argv[1]]()
