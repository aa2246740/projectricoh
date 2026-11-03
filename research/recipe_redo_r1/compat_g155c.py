"""Shared-curve fits against frozen g155c records in separate data contexts."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import fit_one as fit
from entry_codec import predict,record_checks
from fast_backend import load
from full_confirm_support import gate as ordinary_gate
import full_confirm_support
from g155c_baseline import records,PRIVATE,UNITS

ORIGINAL_LOCAL=rt.LOCAL
TARGETS={'a12-50':(20,21,22,24,26),'mount-a12':(20,22,23,24,26)}
FAMILIES=('free','reuse_tone_matrix','reuse_hue_matrix')
ENGINE,SOLVER=load()


def context(family):return ORIGINAL_LOCAL/'compat_g155c'/family


def activate(family):
    root=context(family);root.mkdir(parents=True,exist_ok=True)
    cache=root/'fast_engine';cache.mkdir(exist_ok=True)
    for name in ('adapter_receipt.json','equivalence_task.json'):
        source=ORIGINAL_LOCAL/'fast_engine'/name;target=cache/name
        if not target.exists():shutil.copyfile(source,target)
        assert rt.sha(source)==rt.sha(target)
    rt.LOCAL=root
    return root


def configure(family,template,ui):
    if family!='free':
        from compat_reuse import configure as restrict
        restrict(fit,ENGINE,SOLVER,template,ui,family)


def natural_data(root,unit,index):
    path=root/'targets'/unit/f'{index:02d}_new7.npz'
    return rt.arrays(path) if path.exists() else None


def gate_with_natural(source,final,groups,ui):
    unit=UNITS[ui];extra=natural_data(rt.LOCAL,unit,source['index'])
    if extra is not None:groups=dict(groups,photo_new7_RAW_diagnostic=extra)
    return ordinary_gate(source,final,groups,ui)


def score_seed(root,unit,index,entry,parameters,template,meta,source,ordinal):
    ui=UNITS.index(unit);cam=rt.Camera(ui);gradients,rings=fit.quality.fixtures(cam)
    quality=fit.guard(cam,entry,template,gradients,rings,ui,False)
    if not quality['passes']:return
    base=root/'targets'/unit;groups={g:rt.arrays(base/f'{index:02d}_{g}.npz') for g in meta['input_file_sha256']}
    scores,per_scene,gains={},{},{}
    photo_info=rt.read(root/'inputs'/unit/'photos.json')
    destination=root/'fits'/unit/f'{index:02d}'/f'L0_shared_seed_{ordinal:02d}'
    destination.parent.mkdir(parents=True,exist_ok=True)
    for group,data in groups.items():
        if not len(data['x']):scores[group]=None;continue
        prediction=predict(entry,data['x'],ui)
        scores[group]=dict(candidate=rt.score(data['base'],prediction,data['want']),
            current=rt.score(data['base'],data['current'],data['want']),
            legacy_transferred=rt.score(data['base'],data['legacy_transferred'],data['want']))
        scores[group]['candidate']['weighted_de00_square']=fit.objective(prediction,data['want'],data['sw'])
        a,b=scores[group]['candidate']['similarity_percent'],scores[group]['current']['similarity_percent']
        gains[group]=None if a is None or b is None else a-b
        if group.startswith('photo_'):
            scenes=np.array([photo_info[int(i)]['scene_group'] for i in data['photo_id']]);per_scene[group]={}
            for scene in sorted(set(scenes)):
                use=scenes==scene
                per_scene[group][scene]=dict(candidate=rt.score(data['base'][use],prediction[use],data['want'][use]),
                    current=rt.score(data['base'][use],data['current'][use],data['want'][use]))
        np.savez_compressed(destination.parent/(destination.name+'_'+group+'.npz'),prediction=prediction.astype(np.uint8))
    value=scores['train']['candidate']['weighted_de00_square']
    improved=value<fit.objective(groups['train']['current'],groups['train']['want'],groups['train']['sw'])-1e-9
    primary=scores['photo_iso200']
    doc=dict(label='电脑预测',unit=unit,index=index,name=meta['name'],level=0,record_encoding_level=0,
        requested_tag='shared_seed',backend='rebased_integer_seed',solver_config='not_solved',
        origin='refit',quality=quality,parameters=parameters,theta=None,axis='existing_shared_rows',status=None,
        gray=False,objective=value,scores=scores,per_scene=per_scene,gain_over_current_pp=gains,
        overfit_flags={g:improved and s['candidate']['de00']['median']>=s['current']['de00']['median'] for g,s in scores.items() if s and g!='train'},
        solver_attempts=[],training_improved=improved,training_only_parameter_selection=True,
        no_holdout_used_to_select_parameters=True,recommend_next_dat_build=bool(improved and primary and
            primary['candidate']['de00']['median']<primary['current']['de00']['median']-1e-9 and
            primary['candidate']['de00']['p95']<=primary['current']['de00']['p95']+.25),
        mount_probe_pending=False,main_eligible=True,S_mode='04 Standard',no_native_bw_selector=True,
        mirror_iso100_curve=True,look_unit_mask=1<<ui,record=record_checks(entry),
        record_path=str(destination.with_suffix('.record552').relative_to(rt.HERE)),
        target_sha256=rt.sha(base/f'{index:02d}.json'),source_template_sha256=meta['template_sha256'],
        baseline_g155c=True,compat_family=meta['compat_family'],seed_source=source,no_dat_built=True)
    destination.with_suffix('.record552').write_bytes(entry);rt.dump(destination.with_suffix('.json'),doc)


def prepare(family):
    root=activate(family);base_records=records();catalog={r['index']:r for r in rt.read(rt.HERE/'target_catalog.json')['definitions']}
    proof=[]
    for unit,indices in TARGETS.items():
        ui=UNITS.index(unit);actual04=next(r for r in base_records[unit] if r['kind']=='builtin' and r['slot']==4)
        assert (rt.HERE/actual04['record_file']).read_bytes()==rt.release_dat().entry_of(ui,4), 'Native04 changed; do not reuse old targets'
        input_root=root/'inputs'/unit;input_root.mkdir(parents=True,exist_ok=True)
        for source in (ORIGINAL_LOCAL/'inputs'/unit).iterdir():
            if source.is_file() and source.suffix in ('.json','.npz') and not (input_root/source.name).exists():
                shutil.copyfile(source,input_root/source.name)
        for index in indices:
            target=root/'targets'/unit/f'{index:02d}.json';assert not target.exists()
            name=catalog[index]['name'];baseline=next(r for r in base_records[unit] if r['kind']=='look' and r['name']==name)
            template=(rt.HERE/baseline['record_file']).read_bytes();assert template[1]==baseline['base05_flags']==1
            configure(family,template,ui)
            oldmeta=rt.read(ORIGINAL_LOCAL/'targets'/unit/f'{index:02d}.json')
            meta=dict(oldmeta,template_hex=template.hex(),template_sha256=baseline['record_sha256'],
                compat_family=family,baseline_g155c=True,baseline_record_file=baseline['record_file'],baseline_look_slot=baseline['slot'],
                expected_flags=1,main_search_level=0,main_control='one shared curve',
                legacy_control_source='Frozen g154 research control only; not the g155c published comparison')
            target.parent.mkdir(parents=True,exist_ok=True)
            for group in meta['input_file_sha256']:
                data=rt.arrays(ORIGINAL_LOCAL/'targets'/unit/f'{index:02d}_{group}.npz')
                data['current']=predict(template,data['x'],ui)
                assert np.array_equal(data['base'],predict(rt.release_dat().entry_of(ui,4),data['x'],ui,round_output=False))
                np.savez_compressed(target.parent/f'{index:02d}_{group}.npz',**data)
            if unit=='mount-a12':
                active=rt.read(rt.HERE/'new7_raw_holdout_summary_L1.json')['artifact_root']
                data=rt.arrays(rt.HERE/active/f'{index:02d}.npz');data['current']=predict(template,data['x'],ui)
                np.savez_compressed(target.parent/f'{index:02d}_new7.npz',**data)
            rt.dump(target,meta)
            seeds=[]
            for path in sorted((ORIGINAL_LOCAL/'fits'/unit/f'{index:02d}').glob('L[01]_*.json')):
                old=rt.read(path)
                if not old.get('parameters') or not old['quality']['passes'] or old['record']['independent_curves']:continue
                parameters=copy.deepcopy(old['parameters'])
                parameters['matrix_q10'][1:]=rt.mm.MatrixRow.from_bytes(template[216:244]).coef[1:].tolist()
                if family!='free':
                    problem=ENGINE.Problem(rt.Camera(ui),np.zeros((1,3)),np.array([[1.,2.,3.]]),
                        np.ones(1),dict(level=0,key='seed'))
                    parameters=problem.packed(fit.seed(problem,fit.encode(template,parameters,level=0,look_unit_mask=1<<ui)))
                    parameters=rt.plain(parameters)
                entry=fit.encode(template,parameters,level=0,look_unit_mask=1<<ui)
                if entry in seeds:continue
                seeds.append(entry);score_seed(root,unit,index,entry,parameters,template,meta,str(path.relative_to(rt.HERE)),len(seeds))
            proof.append(dict(unit=unit,index=index,name=name,baseline_sha256=baseline['record_sha256'],flags=1,
                meta=str(target.relative_to(rt.HERE)),meta_sha256=rt.sha(target),shared_seed_records=len(seeds)))
            print('G155C PREPARED',family,unit,index,name,'shared seeds',len(seeds),flush=True)
    rt.dump(root/'prepare_receipt.json',dict(status='PASS',profiles=proof,published_looks_per_unit=10,
        original_native04_byte_identical=True,all_baselines_actual_g155c=True,no_DAT_built=True))


def selected(root,unit,index):
    from report import select
    return select((root/'fits'/unit/f'{index:02d}').glob('L0_*.json'))


def run(family,unit,index,phase,nfev):
    root=activate(family);meta=rt.read(root/'targets'/unit/f'{index:02d}.json')
    template=bytes.fromhex(meta['template_hex']);configure(family,template,UNITS.index(unit))
    full_confirm_support.gate=gate_with_natural
    if phase=='iterate':
        fit.run(unit,index,0,nfev,'compat_iter_r1',True,'fast')
    else:
        source,doc=selected(root,unit,index);assert doc
        fit.run(unit,index,0,nfev,'compat_full_exact_r1',True,'fast',str(source.relative_to(rt.HERE)),True)
    output=root/'fits'/unit/f'{index:02d}'/('L0_'+('compat_iter_r1' if phase=='iterate' else 'compat_full_exact_r1')+'.json')
    doc=rt.read(output);assert doc['record']['independent_curves'] is False
    entry=output.with_suffix('.record552').read_bytes();assert entry[1]==1
    doc.update(baseline_g155c=True,compat_family=family,expected_base05_flags=1,
        model_context=str(root.relative_to(rt.HERE)),new7_in_additional_exact_gate=unit=='mount-a12')
    rt.dump(output,doc)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('prepare','iterate','confirm'))
    ap.add_argument('--family',choices=FAMILIES,default='free');ap.add_argument('--unit',choices=tuple(TARGETS))
    ap.add_argument('--index',type=int);ap.add_argument('--nfev',type=int,default=100);args=ap.parse_args()
    if args.stage=='prepare':prepare(args.family)
    else:run(args.family,args.unit,args.index,args.stage,args.nfev)
