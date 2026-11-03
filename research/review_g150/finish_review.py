"""Audit review receipts, verify frozen inputs and seal the delivered evidence."""
from pathlib import Path
import argparse,collections,datetime,hashlib,json,plistlib,shutil,subprocess,time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g150')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(name,data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')


def audit():
    scripts=collections.defaultdict(list)
    for p in HERE.rglob('*.py'):
        scripts[sha(p)].append(str(p.relative_to(ROOT)))
    jobs,cases,intervals,missing,native_checks=[],[],[],[],[]
    for p in sorted((HERE/'evidence/receipts').glob('*.json')):
        r=read(p); log=HERE/'evidence'/(r['job']+'.log')
        assert sha(log)==r['log_sha256'],log
        assert r['ended_ns']>=r['started_ns']
        intervals += [(r['started_ns'],1,r['job']),(r['ended_ns'],-1,r['job'])]
        resolved={}
        for name,digest in r['review_scripts'].items():
            assert digest in scripts,(p,name,digest)
            resolved[name]=scripts[digest]
        for o in r['outputs']:
            if not o['exists']:
                missing.append(dict(job=r['job'],path=o['path']));continue
            f=ROOT/o['path'];d=read(f)
            assert sha(f)==o['sha256'] and f.stat().st_mtime_ns==o['mtime_ns']
            assert o['fresh'] and r['started_ns']<=o['mtime_ns']<=r['ended_ns']
            assert d.get('status')==o['status']
            if 'dat_sha256' in d: assert d['dat_sha256']==r['dat_sha256'],f
            if 'case' in d:
                native=d.get('detail',{}).get('native_UI_audit')
                if native is not None:
                    assert native['host_UI_writes']==0 and not native['getter_stub_present'],f
                    assert not [e for e in d.get('file_log',[]) if e.get('op') in ('create','write','rename','delete')],f
                    native_checks.append(dict(path=o['path'],audit=native,file_mutations=0))
                cases.append(dict(job=r['job'],case=d['case'],unit=d['unit'],status=d['status'],
                                  seconds=d['seconds'],dat_sha256=d['dat_sha256'],path=o['path']))
        jobs.append(dict(job=r['job'],status=r['status'],returncode=r['returncode'],seconds=r['seconds'],
                         started_ns=r['started_ns'],ended_ns=r['ended_ns'],timeout=r['timeout_seconds'],
                         slot=r['slot'],source_versions=resolved))
    active=set(); peak=0
    for at,change,name in sorted(intervals):
        if change==1:active.add(name);peak=max(peak,len(active))
        else:active.remove(name)
    assert peak<=2 and not active
    for slot in (0,1):
        rows=sorted((j for j in jobs if j['slot']==slot),key=lambda j:j['started_ns'])
        assert all(a['ended_ns']<=b['started_ns'] for a,b in zip(rows,rows[1:]))
    retained=read(HERE/'evidence/implementation-audit.json')
    proof_specs=[
        ('g139-fixed-held-busy-ok','held-busy-ok','50mm'),
        ('g139-fixed-race-at-s-ok','race-at-s-ok','50mm'),
        ('h-50mm-04','held-lock-g150','50mm'),
        ('h-28mm-00','held-lock-g150','28mm'),
        ('h-mount-00','held-lock-g150','mount'),
        ('r-busy-settings-exit-50mm','held-busy-ok','50mm'),
        ('r-transient-busy-half-50mm','transient-busy-fixed','50mm'),
        ('r-record-busy-attempts-50mm','record-busy-once','50mm'),
        ('r-offer-stock-tweak-50mm','offer-stock-tweak-fixed','50mm'),
        ('r-glyph-parent-50mm','glyph-cleanup-contract','50mm')]
    proofs=[]
    for number,(original,case,unit) in enumerate(proof_specs,1):
        negative=next(r for r in retained['failures'] if r['job']==original)
        candidates=[c for c in cases if c['case']==case and c['unit']==unit and c['status'].startswith('PASS')]
        if candidates:
            positive=candidates[-1];fresh=True;path=ROOT/positive['path']
        else:
            assert unit=='28mm' and case=='held-lock-g150'
            path=ROOT/'research/g150/tests/local/f-held-lock-g150-28mm/checks/28mm-held-lock-g150.json'
            positive=read(path);fresh=False
        assert positive['status'].startswith('PASS')
        proofs.append(dict(number=number,original_job=original,original_status=negative['status'],
                           positive_status=positive['status'],positive_path=str(path.relative_to(ROOT)),
                           positive_sha256=sha(path),rerun_in_this_review=fresh))
    save('evidence/ten-fail-evidence.json',dict(status='PASS_EVIDENCE_AUDIT',rows=proofs))
    statuses=collections.Counter(f['status'] for r in retained['regressions'] for f in r.get('result_files',[]) if isinstance(f.get('status'),str))
    assert all(s.startswith('PASS') for s in statuses),statuses
    save('evidence/regression-result-audit.json',dict(status='PASS_RECORD_AUDIT',status_counts=statuses,
         completed_groups=retained['completed_groups'],completed_by_unit=retained['completed_by_unit'],
         scope='retained implementation results; no new regression execution'))
    save('evidence/native-input-audit.json',dict(status='PASS_AUDIT',cases=native_checks))
    save('evidence/review-receipt-audit.json',dict(status='PASS_AUDIT',jobs=jobs,cases=cases,
         case_counts=collections.Counter(c['status'] for c in cases),concurrency_peak=peak,
         missing_outputs=missing,source_versions_resolved=True,
         script_elapsed_sum_s=round(sum(j['seconds'] for j in jobs),3)))
    lines=['# 本轮执行记录','', '| 作业 | 用例 | 单元 | 原始状态 | 秒 | DAT |',
           '| --- | --- | --- | --- | ---: | --- |']
    for c in sorted(cases,key=lambda c:(c['job'],c['case'])):
        lines.append('| {job} | {case} | {unit} | {status} | {seconds} | {dat} |'.format(**c,dat=c['dat_sha256'][:8]))
    (HERE/'RUNS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(jobs=len(jobs),cases=len(cases),counts=collections.Counter(c['status'] for c in cases),peak=peak)))


def seal(clean):
    mount=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert mount['MountPoint']=='/Volumes/Workspace' and mount['FilesystemType']=='apfs'
    assert mount['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and mount['WritableVolume']
    frozen=read(HERE/'evidence/frozen-inputs.json'); changed=[]
    for name,digest in frozen.items():
        p=ROOT/name
        if not p.is_file() or sha(p)!=digest:changed.append(name)
    top=sorted({str(Path(name).parts[0]+'/'+Path(name).parts[1]) for name in frozen})
    now={str(p.relative_to(ROOT)) for folder in top for p in (ROOT/folder).rglob('*') if p.is_file()}
    added=sorted(now-set(frozen));removed=sorted(set(frozen)-now)
    assert not changed and not added and not removed,(changed,added,removed)
    rows=(ROOT/'research/g150/SHA256SUMS').read_text().splitlines()
    assert len(rows)==467
    for line in rows:
        digest,name=line.split('  ',1);assert sha(ROOT/name)==digest,name
    cleanup=dict(requested=clean,path=str(TMP),present_before=TMP.exists())
    if clean:
        assert TMP.name=='review-g150' and TMP.parent==Path('/Volumes/Workspace/Scratch/tmp/projectricoh')
        assert not TMP.is_symlink()
        cleanup['files_removed']=sum(p.is_file() for p in TMP.rglob('*'))
        cleanup['bytes_removed']=sum(p.stat().st_size for p in TMP.rglob('*') if p.is_file())
        if TMP.exists():shutil.rmtree(TMP)
    cleanup['present_after']=TMP.exists()
    receipt=read(HERE/'evidence/input-receipt.json')
    started=datetime.datetime.fromisoformat(receipt['started_utc'].replace('Z','+00:00'))
    ended=datetime.datetime.now(datetime.timezone.utc)
    result=dict(status='PASS_SEAL',frozen_files=len(frozen),manifest_items=467,changed=changed,added=added,removed=removed,
                volume_uuid=mount['VolumeUUID'],profile_sha256=sha(HERE/'offline.sb'),cleanup=cleanup,
                started_utc=started.isoformat(),ended_utc=ended.isoformat(),
                elapsed_wall_seconds=round((ended-started).total_seconds(),3))
    save('evidence/seal.json',result);print(json.dumps(result))


def manifest():
    target=HERE/'SHA256SUMS'
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and p!=target)
    target.write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in paths))
    for line in target.read_text().splitlines():
        digest,name=line.split('  ',1);assert sha(ROOT/name)==digest,name
    print(json.dumps(dict(items=len(paths),manifest_sha256=sha(target))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('audit','seal','manifest'))
    parser.add_argument('--clean',action='store_true');args=parser.parse_args()
    if args.mode=='audit':audit()
    elif args.mode=='seal':seal(args.clean)
    else:manifest()
