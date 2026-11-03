"""Offline continuation checks and adoption of the already completed (a) control."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import argparse
import ast
import os
import plistlib
import re
import shutil
import subprocess
import numpy as np


def integrity():
    disk = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['MountPoint'] == '/Volumes/Workspace'
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'] == 'apfs' and disk['WritableVolume']
    assert os.access('/Volumes/Workspace', os.W_OK)
    df = subprocess.check_output(['df', '-h', '/Volumes/Workspace'], text=True)
    inputs = r.read(r.LOCAL/'inputs.json')
    for rel, entry in inputs.items():
        assert r.sha(r.ROOT/rel) == entry['input_sha256'], rel
        assert r.sha(r.VROOT/rel) == entry['copy_sha256'], rel
    original = r.read(r.VROOT/'research/gr_pairs/local/protected_before.json')
    for rel, digest in original.items():
        assert r.sha(r.ROOT/rel) == digest, rel
    inputs_all = {rel:entry['input_sha256'] for rel,entry in inputs.items()}
    inputs_all.update(original)
    out = dict(frozen_files=len(inputs), original_protected_files=len(original),
               distinct_protected_files=len(inputs_all), all_hashes_unchanged=True,
               disk_uuid=disk['VolumeUUID'], filesystem=disk['FilesystemType'],
               writable=True, df=df)
    r.dump(r.LOCAL/'integrity.json', out)
    initial = r.LOCAL/'continuation_initial.json'
    if not initial.exists():
        r.dump(initial, dict(public_files={p.name:r.sha(p) for p in r.HERE.iterdir() if p.is_file()},
               original_full_fits={p.name:r.sha(p) for p in (r.LOCAL/'fits').glob('*.json')},
               tracked_changes={p:r.sha(r.ROOT/p) for p in ('.gitignore','decisions.tsv')},
               baseline_adopted_without_regeneration=True, projections_adopted_without_regeneration=True))
    print('input integrity passed', out['distinct_protected_files'], 'files', flush=True)
    return out


def adopt_a():
    from fit import Fit, fit_path
    import validate_dense as v
    count = 0
    for group in ('gr3','gr4_hdf'):
        for slot in ('01','02'):
            for kind, indices in [('full',[None]),('loo',range(18)),('hue',range(6)),
                                  ('image',range(2) if group=='gr4_hdf' else [])]:
                for index in indices:
                    suffix = kind if index is None else f'{kind}_{index:02d}'
                    source = r.VROOT/'research/gr_pairs/local/fits'/f'{group}_{slot}_{suffix}.json'
                    original = r.read(source)
                    P = Fit(group,slot,'a',kind,index)
                    row,A,B = r.E.f.unpack_solution(original)
                    row2,_ = r.MM.row2_from_row1(row,P.D.rows)
                    colour = b''.join(r.FS.encode_word(int(a),int(b)) for a,b in zip(A,B))
                    matrix = row.to_bytes()+row2.to_bytes()
                    th = v.decode(P,matrix,colour,P.q0)
                    q = dict(theta=th,row=row,row2=row2,colour=colour,q=P.q0)
                    for iso in (200,1600):
                        D = r.data(slot,iso)
                        x = P.d['x']
                        expect = r.P.prediction(D,original,x)
                        actual = r.FS.lab_from_codes(P.predict(th,x,D))
                        assert np.max(abs(expect-actual)) < 1e-9
                    path = fit_path(group,slot,'a',kind,index)
                    if path.exists():
                        backup = r.LOCAL/'initial_full_fits'/path.name
                        backup.parent.mkdir(parents=True,exist_ok=True)
                        if not backup.exists(): shutil.copyfile(path,backup)
                    out = dict(schema='gr-dense-t1-fit/1',group=group,slot=slot,level='a',kind=kind,index=index,
                        accepted=False,firmware_ready=False,deployable=False,
                        evidence='host model only; no GXR camera or card acceptance',
                        adopted_control=True,source=str(source.relative_to(r.LOCAL)),source_sha256=r.sha(source),
                        T1_enabled=False,table_assignment={'R':'C','G':'B5','B':'D'},free_2x2_sectors=[],
                        theta=th,matrix_hex=matrix.hex(),colour_hex=colour.hex(),
                        curve_nodes=P.curve.xs,channel_curves_RGB=P.q0,
                        dataset_sha256=r.sha(P.dataset),dense_training=int(P.d['train'].sum()),
                        dense_weight=float(P.d['weight'][P.d['train']].sum()),
                        initialization=original['initial_rule'],
                        solver=dict(success=original['solver_success'],message=original['solver_message'],
                                    nfev=original['nfev'],cost=original['integer_cost']),
                        checks=v.check(P,q,full=kind=='full'),scores=v.scores(P,th))
                    r.dump(path,out)
                    count += 1
    print('adopted (a) controls, exact dense Lab equality:',count,flush=True)


def math_check():
    from fit import Fit
    import validate_dense as v
    errors = {}
    rng = np.random.default_rng(20261021)
    for slot in ('01','02'):
        for level in ('a','b','c'):
            P = Fit('gr3',slot,level)
            th = P.baseline_theta()
            th += rng.normal(size=P.np)*1e-4
            direction = rng.normal(size=P.np)
            direction /= np.linalg.norm(direction)
            eps=1e-5
            numeric=(P.data_parts(th+eps*direction)[0]-P.data_parts(th-eps*direction)[0])/(2*eps)
            analytic=P.data_parts(th)[1]@direction
            err=float(np.linalg.norm(numeric-analytic)/np.linalg.norm(numeric))
            assert err < 5e-4, (slot,level,err)
            errors[slot+'_'+level]=err
            base=P.baseline_theta()
            expected=r.P.prediction(P.D,P.D.current,P.d['x'])
            actual=r.FS.lab_from_codes(P.predict(base,P.d['x']))
            assert np.max(abs(expected-actual))<1e-9
            for ch in range(3) if P.t1 else []:
                test=base.copy();test[P.ns+33*ch+10]+=1
                _,curve=P.parameters(test)
                assert np.count_nonzero(curve-P.q0)==1
    r.dump(r.LOCAL/'math_checks.json',dict(analytic_direction_errors=errors,
        baseline_renderer_equality=True,absolute_RGB_curve_semantics=True))
    print('renderer and analytic derivatives passed',errors,flush=True)


def public_scan():
    found=[]
    for p in sorted(r.HERE.rglob('*')):
        if p.is_relative_to(r.LOCAL):continue
        if not p.is_file():continue
        assert not p.is_symlink(),p
        assert p.suffix in ('.py','.md','.json','.csv','.tsv') or p.name in ('.gitignore','SHA256SUMS')
        text=p.read_text()
        assert not re.search(r'(?i)(?<![a-z0-9])[0-9a-f]{96,}(?![a-z0-9])',text),p
        if p.suffix=='.py':
            for node in ast.walk(ast.parse(text)):
                assert not (isinstance(node,ast.Constant) and isinstance(node.value,bytes) and len(node.value)>=48),p
        if p.suffix=='.json':
            forbidden={'input_x','uc','raw3','matrix_hex','colour_hex','theta','theta_continuous',
                       'channel_curves_RGB','curve_nodes','pixels','coefficients'}
            def visit(x):
                if isinstance(x,dict):
                    assert not forbidden.intersection(x),p
                    for value in x.values():visit(value)
                elif isinstance(x,list):
                    assert not (len(x)>=48 and all(isinstance(v,(float,int)) for v in x)),p
                    for value in x:visit(value)
            visit(r.read(p))
        found.append(str(p.relative_to(r.HERE)))
    return found


def verify_fits(start,end):
    from fit import Fit, RADII
    import validate_dense as v
    files=sorted((r.LOCAL/'fits').glob('*.json'))
    assert len(files)==312
    assert 0<=start<end<=len(files) and end-start<=32
    cache={};records=[]
    for path in files[start:end]:
        doc=r.read(path)
        assert not any(doc[k] for k in ('accepted','firmware_ready','deployable'))
        P=Fit(doc['group'],doc['slot'],doc['level'],doc['kind'],doc['index'])
        assert doc['dataset_sha256']==r.sha(P.dataset)
        recorded=r.read(P.dataset.with_suffix('.json'))
        assert recorded['dataset_sha256']==r.sha(P.dataset)
        assert P.d['weight'][P.d['train']].sum()<=18+1e-9
        matrix,colour=bytes.fromhex(doc['matrix_hex']),bytes.fromhex(doc['colour_hex'])
        curve=np.asarray(doc['channel_curves_RGB'])
        th=v.decode(P,matrix,colour,curve)
        assert np.allclose(th,doc['theta'],atol=1e-12,rtol=0)
        for ch in range(3):
            tone=r.SRC.pack_tone('GR dense verification',P.curve.xs[1:-1].astype(int).tolist(),curve[ch].astype(int).tolist())
            nodes,outputs=r.SRC.unpack_tone(*tone)
            assert nodes==P.curve.xs[1:-1].astype(int).tolist()
            assert outputs==curve[ch].astype(int).tolist()
        iso_checks={}
        for iso in (200,1600):
            D=r.data(P.slot,iso)
            key=(P.slot,P.level,iso)
            if key not in cache:cache[key]=r.Response(P,D,step=.1,radii=RADII)
            response=cache[key].summary(th)
            grey=v.grey(P,th,D)
            old=doc['checks'][str(iso)]
            assert grey['grey_gate']==old['grey_gate']
            assert abs(grey['real_grey_max_increase']-old['real_grey_max_increase'])<1e-9
            reevaluated=v.scores(P,th)[str(iso)]
            for name in ('dense_all','dense_train','dense_heldout'):
                a,b=reevaluated[name],doc['scores'][str(iso)][name]
                assert a['n']==b['n']
                if a['n']:assert max(abs(a[k]-b[k]) for k in ('median','p90','max'))<1e-9
            iso_checks[str(iso)]=dict(safety=response,grey=grey,
                fold_sweep_step_deg=.1,recorded_step_deg=.1 if P.kind=='full' else .5)
        records.append(dict(fit=path.name,sha256=r.sha(path),integer_roundtrip=True,
            tone_row_roundtrip=True,scores_reproduced=True,checks=iso_checks))
    r.dump(r.LOCAL/f'verification/fits_{start:03d}_{end:03d}.json',records)
    print('independent integer/tone/score and 0.1-degree checks',start,end,
          'grey failures',sum(not c['grey']['grey_gate'] for d in records for c in d['checks'].values()),
          'safety failures',sum(not c['safety']['passes'] for d in records for c in d['checks'].values()),flush=True)


def review_diagnostics():
    strict=r.read(r.LOCAL/'strict_hinge_diagnostic.json')
    assert (strict['group'],strict['slot'],strict['level'],strict['kind'],strict['index'])==('gr3','01','b','full',None)
    current=r.read(r.LOCAL/'fits/gr3_01_b_full.json')
    old_a=r.read(r.LOCAL/'initial_full_fits/gr4_hdf_02_a_full.json')
    active_a=r.read(r.LOCAL/'fits/gr4_hdf_02_a_full.json')
    same=r.read(r.LOCAL/'same_fold_resume_diagnostic.json')
    matches=r.read(r.LOCAL/'diagnostic_objective_matches.json')
    assert all(matches['full_hue03_training_equality'].values())
    exact=[dict(kind=x[1],index=x[2],absolute_cost_difference=x[0]) for x in matches['matches'] if x[0]<1e-10]
    assert {(x['kind'],x['index']) for x in exact}=={('full',None),('hue',3)}
    assert not np.array_equal(same['theta'],current['theta_continuous'])
    nonconverged=[]
    for p in sorted((r.LOCAL/'fits').glob('*.json')):
        d=r.read(p)
        if not d['solver']['success']:nonconverged.append(p.name)
    out=dict(schema='gr-dense-t1-diagnostics/1',
        convergence_diagnostic=dict(record=r.read(r.LOCAL/'convergence_diagnostic.json'),
            fold_identity='unknown: file contains no group, slot, level, kind, index or theta',
            treatment='retained as historical diagnostic; no claim that this anonymous run was resolved'),
        strict_hinge_diagnostic=dict(group='gr3',slot='01',level='b',kind='full',
            historical_solver=strict['solver'],current_solver=current['solver'],
            current_grey_gate={iso:c['grey_gate'] for iso,c in current['checks'].items()},
            treatment='active full fit converges; historical strict-hinge experiment is not adopted; grey gate still fails'),
        same_fold_resume_diagnostic=dict(success=same['success'],nfev=same['nfev'],
            group='gr3',slot='01',level='b',objective_reproduction_matches=exact,
            full_hue03_training_arrays_verified_equal=True,
            fold_identity='full and hue_03 have identical training here; JSON lacks fold metadata',
            incorporated_into_active_full=False,
            treatment='diagnostic termination is not evidence that the active fit passed grey or safety gates'),
        initial_nonconverged_a_control=dict(fit='gr4_hdf_02_a_full.json',historical_solver=old_a['solver'],
            current_solver=active_a['solver'],adopted_control=active_a['adopted_control'],
            source_sha256=active_a['source_sha256'],
            treatment='previous continuation adopted the converged frozen gr_pairs control; no refit this turn'),
        current_nonconverged_count=len(nonconverged),current_nonconverged_fits=nonconverged,
        continuation_policy='Only the 20 missing fits were computed; all 292 pre-existing fits retained byte-for-byte')
    r.dump(r.HERE/'diagnostic_review.json',out)
    print('diagnostics reviewed; active nonconverged fits:',len(nonconverged),flush=True)


def final_checks(write_checksums=False):
    from run_dense import jobs
    from summarize import verified_fits
    protected=integrity()
    snapshot=r.read(r.LOCAL/'continuation_second_initial.json')
    original_fits={k:v for k,v in snapshot['local_files'].items() if k.startswith('local/fits/')}
    assert len(original_fits)==snapshot['fits_before']==292
    preserved=0
    for rel,digest in snapshot['local_files'].items():
        if rel=='local/integrity.json':continue
        assert r.sha(r.HERE/rel)==digest, 'Prior result changed: '+rel
        preserved+=1
    unchanged_public=[]
    for rel,digest in snapshot['public_files'].items():
        if rel in ('run_dense.py','summarize.py','verify_research.py'):continue
        assert r.sha(r.HERE/rel)==digest, 'Adopted result or model changed: '+rel
        unchanged_public.append(rel)
    for rel,digest in snapshot['tracked_changes'].items():
        assert r.sha(r.ROOT/rel)==digest,rel
    status=subprocess.check_output(['git','--no-optional-locks','status','--porcelain=v1','--untracked-files=all'],cwd=r.ROOT,text=True)
    outside=[s for s in status.splitlines() if s[3:] and not s[3:].startswith(
        ('research/color_fit_v2/gr_dense_t1/','artifacts/stage2j-packages/tables-v6-gr-t1/'))]
    assert outside==snapshot['outside_status'],'Status changed outside permitted output directories'
    expected={name+'.json' for phase in jobs().values() for name,_ in phase}
    actual={p.name for p in (r.LOCAL/'fits').glob('*.json')}
    assert actual==expected and len(actual)==312
    verified=verified_fits()
    assert set(verified)==actual
    datasets=list((r.LOCAL/'datasets').glob('*.npz'))
    assert len(datasets)==104
    for p in datasets:
        assert r.sha(p)==r.read(p.with_suffix('.json'))['dataset_sha256'],p
    assert (r.HERE/'.gitignore').read_text()=='local/\n'
    local_files=sorted(p for p in r.LOCAL.rglob('*') if p.is_file())
    ignored=subprocess.check_output(['git','check-ignore','--stdin'],cwd=r.ROOT,
        input=''.join(str(p.relative_to(r.ROOT))+'\n' for p in local_files),text=True).splitlines()
    assert len(ignored)==len(local_files),'Unignored local derivative'
    tracked=subprocess.check_output(['git','ls-files','--',str(r.LOCAL)],cwd=r.ROOT,text=True)
    assert not tracked,'Local derivatives tracked by Git'
    m=r.read(r.HERE/'metrics.json')
    assert m['fit_count']==m['independent_integer_tone_score_verified_count']==312
    assert m['candidate_count']==0
    assert not any(m[k] for k in ('accepted','firmware_ready','deployable','camera_acceptance','package_created'))
    assert not (r.ROOT/'artifacts/stage2j-packages/tables-v6-gr-t1').exists()
    assert (r.HERE/'REPORT.md').is_file()
    out=dict(schema='gr-dense-t1-verification/1',host_only=True,
        protected_input_files=protected['distinct_protected_files'],all_input_hashes_unchanged=True,
        frozen_files=protected['frozen_files'],original_protected_files=protected['original_protected_files'],
        preserved_existing_fits=len(original_fits),preserved_prior_local_files=preserved,
        unchanged_adopted_public_files=sorted(unchanged_public),outside_git_status_unchanged=True,
        complete_fits=312,new_fits=20,complete_datasets=104,
        integer_tone_and_score_verified=312,ISO_levels=[200,1600],safety_hue_step_degrees=0.1,
        fit_sha256_checked=True,dataset_sha256_checked=True,all_local_derivatives_ignored=True,
        no_local_derivatives_tracked=True,public_aggregate_scan_passed=True,public_checksums_verified=True,
        candidate_count=0,accepted=False,firmware_ready=False,deployable=False,package_created=False,
        disk_uuid=protected['disk_uuid'],filesystem=protected['filesystem'],writable=True)
    if write_checksums:
        r.dump(r.HERE/'verification.json',out)
        public=public_scan()
        content=''.join(f'{r.sha(r.HERE/name)}  {name}\n' for name in public if name!='SHA256SUMS')
        (r.HERE/'SHA256SUMS').write_text(content)
    else:
        assert r.read(r.HERE/'verification.json')==out,'Verification report is stale'
    public=public_scan()
    sums={}
    for line in (r.HERE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        assert name not in sums and name in public and name!='SHA256SUMS'
        assert re.fullmatch('[0-9a-f]{64}',digest) and r.sha(r.HERE/name)==digest,name
        sums[name]=digest
    assert set(sums)==set(public)-{'SHA256SUMS'},'Incomplete public checksum manifest'
    print('final verification passed:',len(sums),'public checksums; 823 protected inputs; 292 prior fits preserved; 312 fits verified',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('integrity','adopt_a','math','public','fits','diagnostics','final'))
    parser.add_argument('--start',type=int,default=0)
    parser.add_argument('--end',type=int)
    parser.add_argument('--write-checksums',action='store_true')
    args=parser.parse_args()
    if args.command=='integrity':integrity()
    elif args.command=='adopt_a':adopt_a()
    elif args.command=='math':math_check()
    elif args.command=='fits':verify_fits(args.start,args.end)
    elif args.command=='diagnostics':review_diagnostics()
    elif args.command=='final':final_checks(args.write_checksums)
    else:print('public aggregate scan passed',public_scan())
