"""Verify frozen sources, collect review identities, and record completed processes."""
from pathlib import Path
import collections,datetime,hashlib,json,os,shutil,subprocess,time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2')
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    evidence=OUT/'evidence'
    initial=read(TMP/'input-initial.json');final=read(TMP/'input-final.json')
    assert initial['rows']==final['rows']==27802 and not initial['errors'] and not final['errors']
    assert initial['manifest_sha256']==final['manifest_sha256']
    assert read(TMP/'input-files-initial.json')==read(TMP/'input-files-final.json')
    for name in ('verify_inputs.py','prepare.py','input-initial.json','input-final.json','input-files-initial.json','input-files-final.json'):
        shutil.copyfile(TMP/name,evidence/name)
    protected=read(evidence/'protected-before.json');current={}
    for directory in ('tools/native_harness','tools/gxr_emulator_batch'):
        for p in sorted((ROOT/directory).rglob('*')):
            if p.is_symlink():current[str(p.relative_to(ROOT))]={'kind':'symlink','target':str(p.readlink())}
            elif p.is_file():current[str(p.relative_to(ROOT))]={'kind':'file','sha256':sha(p)}
    prior=protected['files']
    changed=[name for name in prior.keys()|current.keys() if prior.get(name)!=current.get(name)]
    (evidence/'protected-after.json').write_text(json.dumps({'files':current,'changed':changed,'matched':not changed},indent=2)+'\n')
    assert not changed
    copies=[]
    for relative in ('evidence/copies.json','evidence/copied-busy.json','observation/copies.json','evidence/original-replay-copies.json','evidence/switch-copy.json'):
        value=read(OUT/relative)
        for row in value if isinstance(value,list) else [value]:
            p=ROOT/row['source']
            if p.is_relative_to(OUT):continue
            copies.append({'source':row['source'],'expected':row['source_sha256'],'actual':sha(p)})
    assert all(r['expected']==r['actual'] for r in copies)
    (evidence/'external-copy-sources-final.json').write_text(json.dumps(copies,indent=2)+'\n')
    build=read(ROOT/'tools/speedlab/harness_release_r4/local/ccore/build.json')
    assert sha(Path(build['library']))==build['sha256']
    assert all(sha(Path(p))==v for p,v in build['sources'].items())
    controls=OUT/'frozen-controls';controls.mkdir(exist_ok=True)
    for source in (TMP/'switch/version4-core.c',TMP/'switch/version4-build.json',TMP/'switch'/Path(build['library']).name,TMP/'mutation'/Path(build['library']).name):
        label=('api4-' if source.parent.name=='switch' else 'event-check-removed-')+source.name
        shutil.copyfile(source,controls/label)
    obs=read(OUT/'comparisons/observations/summary.json');assert obs['passed']
    stored=read(OUT/'comparisons/stored/summary.json');assert stored['passed']
    before=read(OUT/'comparisons/before/summary.json');assert before['passed']
    labels=read(OUT/'comparisons/labels/summary.json');assert labels['passed']
    real=read(OUT/'comparisons/real/summary.json')
    accepted=[r for r in real['results'] if 'labels' not in r['job']]+labels['results']
    assert len(accepted)==3 and all(r['equal'] for r in accepted)
    switches=read(OUT/'controls/switch/summary.json');assert switches['passed']
    checked=read(OUT/'entry-controls/verified-summary.json');assert checked['passed']
    identity=read(OUT/'identity-args-r2/summary.json')
    assert identity['matching_resume'] and not identity['changed_driver_reused_old_pass'] and identity['current_input_fresh_c_fails'] and identity['current_input_fresh_python_fails']
    repeats=[]
    for relative in ('subprocess-identity-v2','subprocess-repeat-final-repeat'):
        value=read(OUT/relative/'summary.json')['results'][0]
        assert value['stale_pass_reused'] and value['fresh_both_fail'] and value['fresh_products_equal'] and value['matching_reused'] and value['restored_reused']
        repeats.append({'source':relative,**{k:v for k,v in value.items() if k!='records'}})
    errors=read(evidence/'error-product-comparison.json')
    assert len(errors['errors'])==2 and all(not r['complete_error_product_equal'] and r['logical_backend_paths_still_differ'] and r['error_type_and_message_equal'] for r in errors['errors'])
    replay=read(OUT/'error-product-repeat-sealed/summary.json')
    assert not replay['complete_error_equal'] and replay['frame_counts']=={'python':9,'c':10}
    both_fail_products={}
    for side in ('python','c'):
        run=OUT/'entry/local/runs'/('child-module-driver-v2-fresh-'+side)
        products=list(run.rglob('acceptance.json'));assert len(products)==1
        both_fail_products[side]={'file':str(products[0].relative_to(ROOT)),'sha256':sha(products[0])}
    assert both_fail_products['python']['sha256']==both_fail_products['c']['sha256']
    five_names=[r['job'] for r in before['results']]
    after=[r for r in stored['results'] if r['job'] in five_names]
    five_after={key:sum(r['timing']['c'][key] for r in after) for key in ('wall_seconds','cpu_seconds')}
    ps=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,etime=,command='],text=True)
    active=[]
    for line in ps.splitlines():
        parts=line.split(None,4)
        if len(parts)!=5:continue
        pid=int(parts[0]);command=parts[4]
        executable=command.split(None,1)[0]
        if pid!=os.getpid() and Path(executable).name in ('Python','python3') and ('review_harness_c_switch_r2' in command or 'review-cswitch-r2' in command):active.append(line)
    assert not active,active
    identities={name:sha(ROOT/name) for name in ('tools/native_harness/python_backend.py','firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT','firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT','firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT')}
    data={'verdict':'修改后再采用','initial_manifest':initial,'final_manifest':final,'protected_files':len(current),'protected_changes':changed,
          'copied_external_sources_verified':len(copies),'library_sha256':build['sha256'],'input_identities':identities,
          'observations':[{k:r[k] for k in ('case','equal','compared_values','statuses','packets')} for r in obs['rows']],
          'stored':stored,'before_five':before,'five_after_c':five_after,
          'five_after_wall_ratio':before['timing']['wall_seconds']['python']/five_after['wall_seconds'],
          'real_groups':accepted,'subprocess_repeats':repeats,'fresh_fail_products':both_fail_products,
          'error_product_checks':errors,'switches_passed':True,'checked_entry_controls_passed':True,
          'started_utc':'2026-11-01T13:58:17+00:00','ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'active_review_processes':active,'scratch_retained':str(TMP),'nice':os.getpriority(os.PRIO_PROCESS,0)}
    (evidence/'final-data.json').write_text(json.dumps(data,indent=2)+'\n')
    (evidence/'cleanup.json').write_text(json.dumps({'active_review_processes':active,'computation_finished':True,'scratch_retained_for_reproduction':str(TMP),'protected_files':len(current),'protected_changes':changed},indent=2)+'\n')
    print(json.dumps({k:data[k] for k in ('verdict','protected_files','copied_external_sources_verified','library_sha256','active_review_processes','ended_utc')}))

if __name__=='__main__':main()
