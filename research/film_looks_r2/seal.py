"""Bind the final report, selected records, private banks and replay evidence by SHA256."""
import argparse
import ast
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

assert sys.flags.isolated
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
UNITS=('a12-50','a12-28','mount-a12')


def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def external_runtime_sources():
    # The numerical adapter also imports this pre-existing, archived runtime.
    # Record it explicitly instead of implying freeze.json is exhaustive.
    archive=ROOT/'research/recipe_redo_r1/local/source'
    paths={p for p in archive.rglob('*') if p.is_file() and
           '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    paths.add(ROOT/'research/module_adapt/local/official_parameters.json')
    paths.update(ROOT/'artifacts/firmware/gxr-1.51'/name for name in ('jlaunch3','qlaunch3','l08firm3'))
    paths.update(ROOT/'research/recipe_redo_r1/local/inputs'/unit/'definition.json' for unit in UNITS)
    return [dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)]


def main():
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');args=p.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
    assert os.getpriority(os.PRIO_PROCESS,0)==15
    manifest=LOCAL/'SHA256SUMS'
    if args.verify:
        rows=manifest.read_text().splitlines()
        for line in rows:
            digest,filename=line.split('  ',1)
            assert sha(HERE/filename)==digest,filename
        for line in (HERE/'SHA256SUMS').read_text().splitlines():
            digest,filename=line.split('  ',1)
            assert sha(HERE/filename)==digest,filename
        external=read(LOCAL/'external_runtime_sources.json')['files']
        for row in external:assert sha(ROOT/row['path'])==row['sha256'],row['path']
        print('SEALED FILES VERIFIED',len(rows),'private evidence files')
        return
    summary=read(LOCAL/'summary.json');assert summary['complete']
    library=read(LOCAL/'full_library_manifest.json');assert len(library['records'])==60
    assert read(LOCAL/'capacity.json')['complete_input']
    promotion=read(LOCAL/'locked_shared_flags7_handoff.json')
    assert promotion['status']=='PASS_MODEL_AND_HOST_MATH' and promotion['maximum_RGB_difference']==0.
    assert len(promotion['records'])==3*len(summary['locked_Looks'])
    weighted=read(LOCAL/'weighted_controls_summary.json')
    assert weighted['status']=='COMPLETE_LOCAL_CONTROL_EVALUATION'
    assert weighted['evaluated']==sum(row['weighted']['meets_color_and_overall_budget'] for film in summary['films'] for row in film['units'].values())
    for row in weighted['records']:
        path=LOCAL/'analysis'/f'{row["ordinal"]:02d}'/row['unit']/'final.json'
        assert row['analysis_sha256']==sha(path)
        assert row['record_sha256']==sha(row['record_file'])
        assert row['quantization_branches']==128 and row['reference_exact_checked']
        assert row['runtime_C_flags']['dylib_sha256']==sha(LOCAL/'flags_host.dylib')
        if row['robust_optional_model_candidate']:
            assert row['combined_passes']==128 and sha(row['optional_export'])==row['record_sha256']
    assert read(LOCAL/'master_complete.json')['films']==60
    assert '本报告仍在更新' not in (HERE/'REPORT.md').read_text()
    records=[];points=0;maximum=0.
    for entry in library['records']:
        assert sha(entry['record_file'])==entry['record_sha256']
        assert entry['flags']==7 and entry['record_bytes']==552 and entry['reference_exact_checked']
        assert entry['selected_route'] in ('scene_rgb_matrix','scene_structure')
        film=next(x for x in summary['films'] if x['id']==entry['id'])
        receipt=read(LOCAL/'final_verification'/f'{film["ordinal"]:02d}'/(entry['unit']+'.json'))
        analysis=LOCAL/'analysis'/f'{film["ordinal"]:02d}'/entry['unit']/'final.json'
        assert receipt['status']=='PASS' and receipt['analysis_sha256']==sha(analysis) and receipt['runtime_C_flags_checked']
        assert any(x['record_sha256']==entry['record_sha256'] for x in receipt['records'])
        points+=receipt['points'];maximum=max(maximum,receipt['maximum_literal_RGB_difference'])
        records.append(dict(id=entry['id'],unit=entry['unit'],sha256=entry['record_sha256'],
                            quantization_passes=entry['quantization_passes'],
                            robust=entry['robust_model_data_candidate']))
    freeze=read(LOCAL/'freeze.json');source_drift=[]
    for row in freeze['files']:
        assert sha(LOCAL/row['frozen'])==row['sha256']
        path=ROOT/row['path']
        if not path.exists() or sha(path)!=row['sha256']:source_drift.append(row['path'])
    assert not source_drift,'Original frozen-source drift: '+repr(source_drift)
    for row in read(LOCAL/'catalog.json')['frozen']:
        assert sha(row['file'])==row['sha256']
    for row in read(LOCAL/'style_source_verification.json')['sources']:
        assert sha(ROOT/row['source'])==row['sha256']
    repair=read(LOCAL/'flags_repair.json')
    assert repair['status']=='APPLIED_AND_PROVED' and repair['maximum_RGB_difference']==0.
    admissions=[read(p) for p in (LOCAL/'admissions').glob('*.json')]
    assert admissions and all(x['nice']==15 and x['load1']<=10 and x['active_before']<x['max_processes'] for x in admissions)
    for path in HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    external=external_runtime_sources()
    (LOCAL/'external_runtime_sources.json').write_text(json.dumps(dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=external,
        scope='Final hashes of the pre-existing archived runtime and native-C040 source dependencies; not a claim that these extra files were copied at study start.'),indent=2)+'\n')
    private=[p for p in LOCAL.rglob('*') if p.is_file() and not p.is_symlink()
             and p.name not in ('SHA256SUMS','final_seal.json','WORK_STATE.json','master_progress.json')
             and not p.name.endswith(('.lock','.tmp')) and '.tmp.' not in p.name]
    names=[str(p.relative_to(ROOT)) for p in private]
    ignored=subprocess.run(['git','check-ignore','-z','--stdin'],cwd=ROOT,
                           input='\0'.join(names)+'\0',text=True,capture_output=True,check=False)
    assert ignored.returncode==0 and set(ignored.stdout.rstrip('\0').split('\0'))==set(names),'Private evidence must be ignored'
    rows=[(sha(p),str(p.relative_to(HERE))) for p in sorted(private)]
    manifest.write_text(''.join(digest+'  '+name+'\n' for digest,name in rows))
    report=dict(schema='gxr-film-r2-final-seal/1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                status='PASS_COMPUTER_RESEARCH',films=20,units=3,full_records=60,style_profiles=48,
                locked_Look_candidates=len(summary['locked_Looks']),
                weighted_control_evaluations=weighted['evaluated'],weighted_robust_optional_records=weighted['robust_optional_records'],
                robust_full_records=sum(x['robust'] for x in records),
                independent_replay_points=points,maximum_literal_RGB_difference=maximum,
                frozen_source_files=len(freeze['files']),original_source_drift=source_drift,
                external_runtime_source_files=len(external),
                external_runtime_sources_sha256=sha(LOCAL/'external_runtime_sources.json'),
                admissions=len(admissions),actual_nice_counts=dict(collections.Counter(x['nice'] for x in admissions)),
                load_and_lease_policy_pass=True,private_files_ignored=len(private),
                private_SHA256SUMS_sha256=sha(manifest),records=records,
                encoding_repair_sha256=sha(LOCAL/'flags_repair.json'),
                shared_Look_flags7_equivalence_sha256=sha(LOCAL/'locked_shared_flags7_handoff.json'),
                official_Acros_handoff_sha256=sha(LOCAL/'acros_official_handoff.json'),
                report_sha256=sha(HERE/'REPORT.md'),
                no_new_DAT_host_or_camera_acceptance=True,new_candidate_camera_exposures=0,
                prior_nice20_attempts_preserved_under='local/history/nice20-first-run')
    (LOCAL/'final_seal.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    public=sorted(p for p in HERE.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    public.append(LOCAL/'final_seal.json')
    (HERE/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(HERE))+'\n' for p in public))
    print('SEALED',len(private),'private files;',len(records),'records;',points,'replay points;',len(admissions),'admissions')


if __name__=='__main__':main()
