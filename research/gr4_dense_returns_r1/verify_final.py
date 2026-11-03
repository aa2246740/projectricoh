#!/usr/bin/env python3
"""Independent saved-artifact replay and read-only input receipt verification."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from fit_positive import modules, R7, FOLDS
import ast
import collections
import subprocess


def main():
    f, direct = modules()
    m = rt.model()
    with np.load(rt.LOCAL/'fit/data.npz', allow_pickle=False) as z:
        data = dict(z)
    records = rt.read('fit/records.json')
    current = rt.model()
    src = rt.s.load('final_saved_parser', rt.ROOT/'firmware/stage2l_switch/tools/deep_sources.py')
    _, bank = src.surface_bank()
    baseline = rt.ROOT/'research/stage2l_leica_0708/local/DEEPTBL_v6_leica.DAT'
    assert rt.sha(baseline) == '53c33f0b8976dfaaa78bb4e39f2c193e86cbed26dd3eaa76e8b16ffe2f6a87ab'
    current.base.entries = {f'{e["slot"]:02d}':e for e in src.parse(baseline.read_bytes(), bank)}
    warm = rt.read(R7/'local/direct/guarded/full/01.json')['candidate']
    testx = np.random.default_rng(20261025).uniform(0,4095,(641,3))
    current_equivalence = float(np.max(abs(current.predict('01',testx)-direct.predict(m,'01',warm,testx))))
    assert current_equivalence < 1e-8
    base_lab = m.fs.lab_from_codes(data['base_rgb'])
    full_old = {'page':[], 'hue':[]}
    max_replay = 0.
    fold_audit = []
    for fold in FOLDS[:-1]:
        doc = rt.read(f'fit/folds/{fold}.json')
        assert doc['candidate']['solver_success'] and all(doc['candidate']['checks'].values())
        assert doc['candidate']['sector_guard']['dense']['passes']
        calpath = R7/f'local/folds/{fold}/calibration.json'
        priorpath = R7/f'local/folds/{fold}/01_prior.json'
        assert rt.sha(calpath) == doc['calibration_sha256'] and rt.sha(priorpath) == doc['prior_sha256']
        x = rt.calibrate.apply_calibration(data['raw'], rt.read(calpath))
        bias, _ = rt.calibrate.prior_bias(rt.read(priorpath), x, '01')
        rgb = dict(current=np.clip(current.predict('01',x,unclipped=True)+bias,0,255),
                   candidate=np.clip(direct.predict(m,'01',doc['candidate'],x,unclipped=True)+bias,0,255))
        held = (data['pages'] == int(fold[4:])) if fold.startswith('page') else data['hue_group'] == int(fold[3:])
        lookup = {(r['frame'],r['patch_id']):i for i,r in enumerate(records)}
        for p in doc['points']:
            i = lookup[p['frame'],p['patch_id']]
            assert held[i] and data['supported'][i]
            for name, tt in [('old', data['old_target']), ('new', data['new_target'])]:
                for key in rgb:
                    e = float(m.fs.delta_e00(m.fs.lab_from_codes(rgb[key][i]), tt[i]))
                    max_replay = max(max_replay, abs(e-p[name][key]))
        assert set(map(tuple,doc['train_keys'])).isdisjoint(set(map(tuple,doc['holdout_keys'])))
        scheme = 'page' if fold.startswith('page') else 'hue'
        for i in np.flatnonzero(held):
            full_old[scheme].append(dict(frame=records[i]['frame'],patch_id=records[i]['patch_id'],
                baseline=float(m.fs.delta_e00(base_lab[i], data['old_target'][i])),
                **{k:float(m.fs.delta_e00(m.fs.lab_from_codes(v[i]),data['old_target'][i])) for k,v in rgb.items()}))
        fold_audit.append(dict(fold=fold,n_train=doc['n_train'],n_holdout=doc['n_holdout'],
            disjoint=True, prior_hash_unchanged=True, calibration_hash_unchanged=True))
    assert max_replay < 1e-9
    old_scores = {scheme:{key:f.score([p[key]for p in pp],[p['baseline']for p in pp])
        for key in ('current','candidate')}for scheme,pp in full_old.items()}
    assert all(len(p)==258 for p in full_old.values())
    rt.dump('fit/old_surrogate_full258.json', old_scores)
    groups=collections.defaultdict(set)
    for r in records:
        groups[r['key']].add(r['hue_group'])
    assert all(len(v)==1 for v in groups.values())
    ns=dict(np=np)
    path=rt.ROOT/'research/gr_pairs/targets.py'
    tree=ast.parse(path.read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='apply_relative')
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),ns)
    from target import relative
    rng=np.random.default_rng(20261025)
    labs=[np.c_[rng.uniform(0,100,1000),rng.uniform(-80,80,(1000,2))]for _ in range(3)]
    labs[0][:20,1:]=0
    relative_difference=float(np.max(abs(relative(*labs)-ns['apply_relative'](*labs))))
    assert relative_difference < 1e-12
    receipts={}
    def consume(mapping):
        for key,digest in mapping.items():
            assert key not in receipts or receipts[key]==digest,(key,'conflicting input hashes')
            receipts[key]=digest
    for p in rt.LOCAL.rglob('*.inputs.json'):
        consume(rt.read(p).get('sha256',{}))
    for p in rt.LOCAL.rglob('input_hashes.json'):
        consume(rt.read(p).get('sha256',{}))
    consume(rt.read(rt.RETURNS/'inputs.json')['sha256'])
    consume(rt.read('host/compile.json')['sources_sha256'])
    mount_host=rt.LOCAL/'mount/host'
    stage=rt.ROOT/'firmware/stage2l_switch'
    assert (mount_host/'deep_isp.c').read_bytes()==(stage/'deep_isp.c').read_bytes()
    header=(stage/'deep_isp.h').read_text()
    assert (mount_host/'deep_isp.h').read_text()==header.replace(
        '#define RFW_STOCK_ENTRY_CRC UINT32_C(0x0d2b0ea9)',
        '#define RFW_STOCK_ENTRY_CRC UINT32_C(0x4686301b)')
    target=rt.read('target/manifest.json')
    consume(target['inputs_sha256'])
    assert target['styles']==['standard','positive'] and target['diagnostic_styles_used'] is False
    identity=rt.read(rt.RETURNS/'partial-main-identities.json')
    assert identity['partial'] and identity['required_styles']==['positive','standard']
    assert identity['original_readback_sha256']==rt.sha(rt.ROOT/'research/gr_dense_reference/readback_r3.py')
    review=rt.read(rt.RETURNS/'partial-gate-review.json')
    assert review['all_passed'] and review['wrapper_sha256']==rt.sha(rt.HERE/'partial_main.py')
    for p in identity['identities']:
        consume({str(Path(p['path']).relative_to(rt.ROOT)):p['sha256']})
    for p in identity['returned_dngs'].values():
        consume({str(Path(p['path']).relative_to(rt.ROOT)):p['sha256']})
    for band in range(1,5):
        diag=rt.read(rt.RETURNS/f'dense-band-{band}-diagnostics.json')
        assert diag['diagnostic_only'] and not diag['target_eligible']
        for p in diag['modes'].values():
            consume({str(Path(p['path']).relative_to(rt.ROOT)):p['sha256']})
    for p in rt.LOCAL.glob('natural/*.json'):
        doc=rt.read(p)
        for extension,key in [('DNG','input_dng_sha256'),('JPG','input_jpeg_sha256')]:
            if key in doc:
                photo=rt.INPUT/'Other'/(doc['stem']+'.'+extension)
                consume({str(photo.relative_to(rt.ROOT)):doc[key]})
    for key,digest in receipts.items():
        assert rt.sha(rt.ROOT/key)==digest,('input changed',key)
    for p in rt.HERE.glob('*.py'):
        compile(p.read_text(),str(p),'exec')
    assert not subprocess.check_output(['git','ls-files','-z',str(rt.LOCAL)],cwd=rt.ROOT)
    subprocess.run(['git','check-ignore','-q',str(rt.LOCAL/'candidate/DEEPTBL_50mm_gr4_positive_r1.DAT')],cwd=rt.ROOT,check=True)
    rt.dump('verification/final.json',dict(all_passed=True,input_files_verified=len(receipts),inputs_sha256=receipts,
        original_readback_unchanged=True,primary_target_excludes_diagnostics=True,
        saved_OOF_error_replay_max_difference=max_replay,
        r7_current_fit_equals_actual53_table_max_RGB_code_difference=current_equivalence,
        relative_transfer_equals_original_max_difference=relative_difference,
        same_colour_key_never_crosses_hue_groups=True,folds=fold_audit,
        private_outputs_not_in_index=True,python=sys.version,python_executable=sys.executable,
        no_camera_or_card_access=True,no_firmware_build=True,no_git_commit=True))
    print('final replay passed; input receipts',len(receipts),'max OOF delta',max_replay,
          'old full258', {s:{k:round(v['similarity_median']*100,2)for k,v in q.items()}for s,q in old_scores.items()},flush=True)


if __name__=='__main__':
    main()
