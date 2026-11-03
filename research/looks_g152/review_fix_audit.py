"""Audit the final review correction, its execution intervals and witnesses."""
from pathlib import Path
import argparse,ast,hashlib,json,os,shutil,struct,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152')
sys.path.insert(0,str(HERE))
from dat_format import sections,u32,expand,expand_effect,CRC_FIELDS,crc
from controller_guard import workers,controller_lease
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def elf_sections(path):
    # Independent byte reader, matching the frozen review's ELF32 reader.
    raw=path.read_bytes();assert raw[:6]==b'\x7fELF\x01\x02'
    start=u32(raw,32);width,count,names=struct.unpack_from('>3H',raw,46)
    headers=[struct.unpack_from('>10I',raw,start+i*width) for i in range(count)]
    row=headers[names];strings=raw[row[4]:row[4]+row[5]]
    return {strings[r[0]:].split(b'\0',1)[0].decode():dict(size=r[5],bytes=raw[r[4]:r[4]+r[5]]) for r in headers}
def check_manifest(path,base):
    count=0
    for line in path.read_text().splitlines():
        value,name=line.split('  ',1);assert sha(base/name)==value,name;count+=1
    return count
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    start=time.time_ns();phase=HERE/'review_fix';initial=read(phase/'start.json');build=read(phase/'build.json')
    package=read(HERE/'package.json');test=package['test']['dat_sha256'];release=package['release']['dat_sha256']
    raw_test=(ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert TMP==Path(os.environ['TMPDIR']) and not TMP.is_symlink()
    expected=read(HERE/'queue-fix-required.json');assert read(HERE/'queue-required.json')==expected
    assert len(expected)==len({j['name'] for j in expected})==62
    missing=[];receipts=[];verified=0
    for job in expected:
        path=HERE/'evidence/jobs'/(job['name']+'.json')
        if not path.is_file():missing.append(job['name']);continue
        r=read(path)
        if r['status']!='PASS':missing.append(job['name'])
        assert r['job']==job and r['dat_sha256']==test
        assert r['started_ns']>=build['ended_ns'] and r['ended_ns']>r['started_ns']
        assert r['command'][:4]==['/usr/bin/nice','-n','10','/usr/bin/sandbox-exec']
        assert r['seconds']>0 and sha(HERE/'evidence/jobs'/(job['name']+'.log'))==r['log_sha256']
        for name in (job['script'],'run_jobs.py','controller_guard.py'):assert sha(HERE/name)==r['scripts'][name],(job['name'],name)
        for output in r['outputs']:
            path=HERE/output['path'];assert output['fresh'] and r['started_ns']<=path.stat().st_mtime_ns<=r['ended_ns']
            assert sha(path)==output['sha256'] and read(path)['status']=='PASS',str(path)
            verified+=1
        receipts.append(r)
    assert args.partial or args.preflight or not missing,missing
    # Include the old-DAT reproduction and any failed attempts in the cap.
    all_runs=[]
    for p in (HERE/'evidence/jobs').glob('fix-*.json'):
        r=read(p)
        if r['started_ns']>=initial['started_ns']:all_runs.append(r)
    events=sorted((stamp,change) for r in all_runs for stamp,change in ((r['started_ns'],1),(r['ended_ns'],-1)))
    current=maximum=0
    for _,change in events:current+=change;maximum=max(maximum,current);assert 0<=current<=2
    assert current==0 and maximum<=2
    fixture=read(phase/'fixture_revision.json');retired_failures=[]
    assert sha(HERE/'review_fix_checks.py')==fixture['unchanged_shared_check_sha256']
    assert sha(HERE/fixture['replacement_script'])==fixture['replacement_script_sha256']
    for name in fixture['retired_jobs']:
        assert name not in {j['name'] for j in expected}
        r=read(HERE/'evidence/jobs'/(name+'.json'))
        assert r['dat_sha256']==test
        if r['status']=='FAIL':
            p=HERE/r['outputs'][0]['path'];assert sha(p)==r['outputs'][0]['sha256']
            assert 'assert cam.h.u(0x2022f5ac,1)==7' in read(p)['error']
            retired_failures.append(name)
    priorities=read(phase/'evidence/process_priorities.json')
    assert priorities['status']=='PASS' and len(priorities['model_processes'])==2
    assert all(r['nice']>=10 for r in priorities['model_processes'])
    for prev,next_phase in (('math','smoke'),('smoke','native'),('native','retry'),('retry','final')):
        handoff=phase/'evidence'/('handoff-'+prev+'.json')
        next_jobs=read(HERE/('queue-fix-'+next_phase+'.json'))
        started=[r['started_ns'] for r in all_runs if r['job']['name'] in {j['name'] for j in next_jobs}]
        if not started:continue
        h=read(handoff);assert h['status']=='PASS' and not h['remaining']
        complete=HERE/'evidence'/('queue-fix-'+prev+'-complete.json')
        assert sha(complete)==h['complete_sha256'] and min(started)>=h['recorded_ns']
    matrix=[]
    final_S_checks=[]
    for unit in ('50mm','mount'):
        path=HERE/'evidence'/('lock-reviewfix-'+unit+'.json')
        if not path.exists():continue
        summary=read(path);assert summary['status']=='PASS' and summary['dat_sha256']==test and summary['cases']==24
        assert summary['transitions']==['builtin-effect','effect-same-base','effect-other-base','effect-builtin']
        assert summary['timings']==['held','race-at-s','transient'] and summary['exits']==['ok','half']
        assert summary['native_UI_audit']['host_UI_writes']==0 and summary['native_UI_audit']['backend'].endswith('/python_backend.py')
        owner=next(r for r in receipts if r['job']['name']=='fix-matrix-'+unit)
        for transition in summary['transitions']:
            for timing in summary['timings']:
                for kind in summary['exits']:
                    p=HERE/'evidence'/f'lock-reviewfix-{unit}-{transition}-{timing}-{kind}.json';d=read(p)
                    assert d['status']=='PASS' and d['dat_sha256']==test and not d['key_S_stores']
                    assert owner['started_ns']<=d['started_ns']<d['ended_ns']<=owner['ended_ns']
                    assert owner['started_ns']<=p.stat().st_mtime_ns<=owner['ended_ns']
                    for stage in ('after_key','after_exit','after_reopen'):
                        for field in ('rows','T','S_sha256'):assert d[stage][field]==d['before'][field],(p,stage,field)
                    for stage in ('after_key','after_reopen'):assert d[stage]['ref_sha256']==d['before']['ref_sha256']
                    matrix.append(dict(path=str(p.relative_to(HERE)),sha256=sha(p)))
    if not (args.partial or args.preflight):assert len(matrix)==48
    for unit in ('50mm','mount'):
        for slot in (4,8):
            p=phase/'evidence'/f'after-refusal-{unit}-{slot}.json'
            if not p.exists():continue
            r=read(p);d=r['detail'];assert r['status']=='PASS' and r['dat_sha256']==test
            assert d['matches']['actual_prior'] and not d['frame']['failed'] and d['flags_after_first_exit']['live_verified']=='00'
            for stage in ('after','after_reopen'):
                for field in ('rows','T','S_sha256'):assert d[stage][field]==d['before'][field]
        for kind in ('effect','photo','multiple'):
            p=phase/'evidence'/(f'photo-final-{unit}.json' if kind=='photo' else f'{kind}-{unit}-state.json')
            if not p.exists():continue
            r=read(p);assert r['status']=='PASS' and r['dat_sha256']==test
            if kind=='photo':
                assert len(r['half_transitions'])==2
                assert all(x['physical_state_unchanged'] and x['live_verified']==0 for x in r['half_transitions'])
                text=(HERE/'review_fix_checks.py').read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='changed_state')
                source=''.join(text.splitlines(True)[node.lineno-1:node.end_lineno])
                assumption='    assert cam.h.u(0x2022f5ac,1)==7\n';assert source.count(assumption)==1
                executed=source.replace(assumption,"    assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\0'\n")
                assert hashlib.sha256(source.encode()).hexdigest()==r['shared_function_sha256']
                assert hashlib.sha256(executed.encode()).hexdigest()==r['executed_function_sha256']
            for change in r['detail']['changes']:
                for field in ('rows','T','S_sha256'):assert change['after'][field]==change['before'][field]
            assert all(x==[] for x in r['detail']['S_stores_during_refusals'])
            # Reconstruct all 4096 S bytes independently, including the
            # remembered builtin record, from a matching raw S witness.
            witness=sorted((HERE/'local/review-fix-runtime/runtime/evidence').glob('after-refusal-*-'+unit+'-before-S.bin'))[0]
            settings=bytearray(witness.read_bytes());assert len(settings)==4096
            assert hashlib.sha256(settings).hexdigest()==r['detail']['changes'][-1]['before']['S_sha256']
            u=0 if unit=='50mm' else 2;directory=u32(raw_test,156)+64*u
            at=u32(raw_test,directory+16)+32+4*64;record=raw_test[at:at+64]
            assert record[3]==1 and record[49:51]==bytes(2)
            settings[0x36e]=record[3];settings[0x6dd:0x6df]=bytes((9,9))
            remembered=bytearray(b'GXR2\1'+bytes((5,u,1))+struct.pack('>10h',100,*([0]*9))+raw_test[20:28])
            remembered+=struct.pack('>I',crc(remembered));assert len(remembered)==40
            settings[0xfd4:0xffc]=remembered;expected_S=hashlib.sha256(settings).hexdigest()
            assert expected_S==r['detail']['final']['S_sha256'],(kind,unit)
            entry=expand(raw_test,u,5)
            assert r['detail']['final']['rows']==[hashlib.sha256(entry[a:a+n]).hexdigest() for a,n,_ in CRC_FIELDS]
            assert r['detail']['final']['T']==int.from_bytes(entry[445:447],'big')
            identity=bytes((record[2],))+record[4:36]+bytes((record[3],))+record[36:51]
            reference=bytes((u,5))+identity+bytes(5);assert len(reference)==56
            assert r['detail']['final']['ref_sha256']==hashlib.sha256(reference).hexdigest()
            final_S_checks.append(dict(kind=kind,unit=unit,expected_S_sha256=expected_S,raw_prior_witness=str(witness.relative_to(HERE))))
    observed=read(phase/'evidence/observed-mount-8.json')
    assert observed['status']=='PASS' and observed['dat_sha256']==initial['prior_test_sha256']
    assert not observed['detail']['observed_review_failure']['contract_pass']
    old_receipt=read(HERE/'evidence/jobs/fix-observed-mount.json')
    assert old_receipt['scripts']['review_fix_checks.py']==sha(phase/'legacy/observed_wrapper.py')
    fmt=read(HERE/'evidence/format_checks.json');isolation=fmt['area_crc_isolation']
    assert fmt['dat_sha256']==test and isolation['header_crc_valid'] and not isolation['area_crc_valid']
    assert isolation['repaired_valid_units']==3 and isolation['accepted_when_only_area_check_removed']
    archive=ROOT/initial['archive'];assert check_manifest(archive/'SHA256SUMS',archive)==initial['prior_files']==559
    assert sha(archive/'SHA256SUMS')==initial['prior_manifest_sha256']
    review=ROOT/'research/review_g152';assert check_manifest(review/'SHA256SUMS',ROOT)==initial['review_files']==153
    assert sha(review/'SHA256SUMS')==initial['review_manifest_sha256']
    for name in ('independent_cases.py','verify_witness.py','REVIEW.md'):assert sha(phase/'legacy'/name)==sha(review/name)
    engine=ROOT/'firmware/engine_v60_g152';changed=[]
    for p in engine.rglob('*'):
        if p.is_file() and not p.is_symlink() and 'local' not in p.parts:
            old=archive/p.relative_to(ROOT);assert old.is_file()
            if sha(p)!=sha(old):changed.append(str(p.relative_to(ROOT)))
    assert changed==[x['path'] for x in build['engine_changes']] and len(changed)==1 and changed[0].endswith('/eng_core.c')
    layout=read(engine/'candidate/local/full-r13/layout.json')
    for p,value in layout['sources'].items():assert sha(ROOT/p)==value,p
    assert sha(engine/'candidate/local/full-r13/GXRCE.DAT')==release
    assert sha(engine/'candidate/local/full-r13/engine.bin')==layout['engine_sha256']
    raw=(ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT').read_bytes()
    linked=elf_sections(engine/'candidate/local/full-r13/engine.elf');at,n=sections(raw)[0]
    assert raw[at:at+n]==raw_test[at:at+n]==linked['.engine']['bytes']
    assert n==package['code_bytes']==64124 and linked['.bss']['size']==u32(raw,116)==package['bss_bytes']==9252
    assert 7504+((len(raw)+u32(raw,116)+3)&~3)==package['main_request']<=107612
    prior=(archive/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT').read_bytes()
    for u in range(3):
        for slot in range(1,9):assert expand(raw,u,slot)==expand(prior,u,slot)
    for effect in range(10):assert expand_effect(raw,effect)==expand_effect(prior,effect)
    assert raw[u32(raw,204)+3392:]==prior[u32(prior,204)+3392:]
    for name,record in read(HERE/'input_receipt.json')['files'].items():assert sha(ROOT/name)==record['sha256'],name
    for name,value in read(HERE/'review_input_receipt.json').items():assert sha(ROOT/name)==value,name
    for package_name,value in (('package_v38_g152',release),('package_v38_g152_test',test)):
        p=ROOT/'firmware'/package_name;assert sha(p/'local/SD_ROOT/GXRCE.DAT')==value
        check_manifest(p/'SHA256SUMS',ROOT)
    guard=read(HERE/'evidence/controller_guard.json')
    assert guard['status']=='PASS' and len(guard['cases'])==4
    for name,value in guard['unchanged_source_sha256'].items():assert sha(HERE/name)==value
    if args.preflight:
        progress=dict(status='IN_PROGRESS',checked_jobs=len(receipts),pending=missing,final_S_checks=final_S_checks,
                      linked_code_matches_packaged_DAT=True,recorded_ns=time.time_ns())
        (phase/'evidence/acceptance_preflight.json').write_text(json.dumps(progress,indent=2)+'\n')
        print(json.dumps(progress));return
    remaining=workers({j['script'] for j in expected});assert not remaining
    with controller_lease(expected):pass
    if TMP.exists():shutil.rmtree(TMP)
    assert not TMP.exists()
    cleanup=dict(status='PASS',path=str(TMP),absent_after=True,ended_ns=time.time_ns())
    (HERE/'cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    result=dict(status='PARTIAL' if missing else 'PASS',incomplete=missing,dat_sha256=release,test_dat_sha256=test,
                required_jobs=62,completed_jobs=len(receipts),outputs_verified=verified,maximum_concurrent_tests=maximum,
                all_phase_jobs=len(all_runs),remaining_test_processes=remaining,testcard_lock_cases=len(matrix),matrix=matrix,
                retired_fixture_failures=retired_failures,
                engine_changes=changed,prior_archive_files=559,review_files_unchanged=153,frozen_inputs_verified=414,
                final_S_and_reference_checks=final_S_checks,
                pool_and_control_bytes_unchanged=True,started_ns=start,ended_ns=time.time_ns())
    result['linked_code_matches_packaged_DAT']=True
    (HERE/'evidence/final_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (phase/'evidence/final_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='matrix'}))
if __name__=='__main__':main()
