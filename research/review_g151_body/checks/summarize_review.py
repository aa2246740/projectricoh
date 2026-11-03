#!/usr/bin/python3 -I
"""Check the completed evidence, compare c0 observations and verify frozen inputs."""
from pathlib import Path
import hashlib
import json

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'research/review_g151_body/evidence'
BODY='71697385bf69283ed6349f8829884e8768ff33be2869f940188b668d782e31fa'
DAT='544211ae84277356f9183f9158ef071349be0a1fab4f68d8c23452530ffc6d5f'
TEST_DAT='5574164cf0f8bf658db9aa1279895b4a7aa2ce4fbe77bdc676d599f4f1d7a8cf'
UNITS=('50mm','28mm','mount')
LOCK_CASES=('held-busy-ok','held-lock-g150','offer-busy','race-at-s-half')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((OUT/name).read_text())


def main():
    resident_sha=sha(ROOT/'firmware/resident_v39/local/resident/build/resident.elf')
    engine_sha=sha(ROOT/'firmware/engine_v59_g151/candidate/local/full-r13/engine.elf')
    fn_engine_sha=sha(ROOT/'firmware/engine_v59_g151/variants/fn-test/candidate/local/full-r13/engine.elf')
    fn_dat_sha=sha(ROOT/'firmware/engine_v59_g151/variants/fn-test/candidate/local/full-r13/GXRCE.DAT')
    static=load('static_review.json')
    assert static['identity']['body_sha256']==BODY
    assert static['dat']['release']==DAT and static['dat']['test']==TEST_DAT
    assert static['dat']['main_request']==105404 and static['dat']['review_margin']==720
    assert all(load('resident_rebuild.json')['comparisons'].values())
    assert load('identity_gate.json')['status']=='PASS'
    assert load('heap_budget.json')['live_extent_total']==108016
    assert load('fn_doc_path.json')['status']=='OBSERVED_P2'
    assert load('fn_doc_path.json')['correct_preflight_passed']
    backends=load('backend_paths.json')
    assert backends['reference_settings']['mode']=='fast' and backends['reference_settings']['batch']
    host=OUT/'host-v39.jsonl'
    assert len(host.read_text().splitlines())==51
    assert host.read_bytes()==(ROOT/'research/body_v39/evidence/host-v39.jsonl').read_bytes()
    replay=load('replay-v39.json')
    old_replay=json.loads((ROOT/'research/body_v39/evidence/replay-v39.json').read_text())
    assert len(replay['cases'])==36 and replay['cases']==old_replay['cases']
    assert replay['elf_sha256']==resident_sha
    assert load('route-50mm-new-ctl-bad.json')['main_request']==105404

    routes={}
    route_cases=('new:g149','new:g150','new:g137','new:g139','new:probe148',
        'c0:g151','v38:g151','new:no-card','new:ctl','new:ctl-bad','new:release','c0:release')
    for case in route_cases:
        run=load('route-50mm-'+case.replace(':','-')+'.json')
        assert run['status']=='PASS' and run['backend']['module']=='python_backend'
        assert run['root_state']==(3 if run['positive'] else 6)
        assert run['rows']==(8 if run['positive'] else 7)
        if 'native_return' in run:assert run['native_return']['ok']
        if not run['positive'] and case!='new:ctl':
            assert run['dat_calls']==dict(rv_engine=0,rv_invoke=0)
            assert run['native_return']['ok'] and not(run['flags']&128)
        routes[case]={k:run[k] for k in ('root_state','rows','flags','dat_calls','dat_sha256')}

    dats,rotations,locks={},{},{}
    for unit in UNITS:
        wrapper=load(f'dat-{unit}-ABCDH.json')
        assert wrapper['status']=='PASS' and all(b['module']=='python_backend' for b in wrapper['backends'])
        run=load(f'dat-body-{unit}.json')
        assert run['body_sha256']==BODY and run['dat_sha256']==DAT
        assert run['resident_elf_sha256']==resident_sha and run['engine_elf_sha256']==engine_sha
        assert run['grain_matrix']['cases']==run['grain_matrix']['identical']==379
        assert run['grain_commit']['cases']==run['grain_commit']['identical']==144
        assert not run['grain_matrix']['differences'] and not run['grain_commit']['differences']
        dats[unit]=dict(seconds=run['seconds'],grain_cases=379,commit_cases=144)
        rotation=load(f'rotate-{unit}-.json')
        assert rotation['status']=='PASS' and all(b['module']=='python_backend' for b in rotation['backends'])
        detail=load(f'dat-rotate-{unit}.json')
        assert detail['engine_elf_sha256']==fn_engine_sha and detail['dat_sha256']==fn_dat_sha
        assert len(detail['steps'])==2 and not detail['stale_rotation']['offered']
        rotations[unit]=dict(seconds=detail['seconds'],dat_sha256=detail['dat_sha256'])
        for case in LOCK_CASES:
            run=load(f'lock-{unit}-{case}.json')
            assert run['status']=='PASS_M32R' and run['backend']['module']=='python_backend'
            assert run['body_sha256']==BODY and run['dat_sha256']==TEST_DAT
            assert run['resident_elf_sha256']==resident_sha and run['engine_elf_sha256']==engine_sha
            locks[unit+':'+case]=dict(seconds=run['seconds'],result=run['details'].get('result'))

    milestone_key=lambda row:tuple(row.get(k) for k in ('label','step','task','path','r0','r4'))
    recovery={}
    names=['review-official','review-new','review-window']
    observations={name:load('recovery-'+name+'.json') for name in names}
    previous={name:json.loads((ROOT/'research/body_v39/evidence'/('recovery-'+name+'.json')).read_text())
              for name in ('yes-official','yes-v39-c0','yes-trap')}
    base=previous['yes-v39-c0']
    sequence=[milestone_key(r) for r in base['milestones']]
    for name,run in {**observations,**previous}.items():
        assert run['steps']==500000000 and run['confirm_phase']['confirm_step']==65975242
        assert not run['hooks_or_resident_executed'] and not run['pc_in_resident_window']
        assert not any(n.startswith(('hook-word','resident')) and count for n,count in run['counts'].items())
        assert run['counts']==base['counts'] and run['library_sha256']==base['library_sha256']
        assert sequence==[milestone_key(r) for r in run['milestones']],name
        assert run['confirm_phase']==base['confirm_phase'] and run['nand_commands']==base['nand_commands']
        recovery[name]=dict(image_sha256=run['image_sha256'],steps=run['steps'],seconds=run['seconds'],
            confirmation_step=run['confirm_phase']['confirm_step'],milestones=len(run['milestones']),
            identical_to_c0=True,full_counters_identical_to_c0=True,library_sha256=run['library_sha256'],
            files_opened=[r['path'] for r in run['milestones'] if r['label']=='file-open'])
    assert observations['review-new']['image_sha256']==BODY
    assert load('window_fixture.json')['trap']==observations['review-window']['image_sha256']==previous['yes-trap']['image_sha256']
    (OUT/'recovery_comparison.json').write_text(json.dumps(recovery,indent=2)+'\n')

    frozen=load('frozen_before.json')
    changed=[]
    for name,value in frozen['files'].items():
        p=ROOT/name
        if 'link' in value:
            ok=p.is_symlink() and str(p.readlink())==value['link']
        else:
            ok=p.is_file() and p.stat().st_size==value['bytes'] and sha(p)==value['sha256']
        if not ok:changed.append(name)
    added=[]
    for name in frozen['roots']:
        for p in (ROOT/name).rglob('*'):
            if (p.is_file() or p.is_symlink()) and str(p.relative_to(ROOT)) not in frozen['files']:
                added.append(str(p.relative_to(ROOT)))
    dependency_changed=[]
    dependencies=load('model_inputs.json')
    for name,value in dependencies.items():
        if sha(ROOT/name)!=value['sha256']:dependency_changed.append(name)
    manifest=ROOT/'research/body_v39/SHA256SUMS'
    receipt=load('inputs_before.json')
    assert sha(manifest)==receipt['manifest_sha256']
    assert receipt['count']==125
    assert all(sha(ROOT/row['path'])==row['expected'] for row in receipt['files'])
    seal=dict(status='PASS' if not(changed or added or dependency_changed) else 'FAIL',
        frozen_records=len(frozen['files']),model_dependencies=len(dependencies),manifest_entries=125,
        manifest_sha256=sha(manifest),changed=changed,added=added,dependency_changed=dependency_changed)
    (OUT/'frozen_verification.json').write_text(json.dumps(seal,indent=2)+'\n')
    assert seal['status']=='PASS',seal
    summary=dict(status='PASS',scope='g151 body rebuild and DAT port, offline only',body_gate='PASS',
        dat_release_gate='WAIT_G152_FIX_AND_DELTA_REVIEW',known_dat_p1_preserved=True,new_p2=1,
        body_sha256=BODY,dat_sha256=DAT,test_dat_sha256=TEST_DAT,
        host_contract_lines=51,machine_code_cases=36,routes=routes,dat_units=dats,
        rotations=rotations,lock_cases=locks,recovery=recovery,frozen=seal)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',routes=len(routes),dat_units=len(dats),rotations=len(rotations),
                         lock_cases=len(locks),new_recovery_runs=3,frozen_records=seal['frozen_records'])))


if __name__=='__main__':
    main()
