"""Forward-only evaluation of frozen Look/full pairs on real RAW input banks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_common import C, R1, same_scene_target, frozen_target, score


def region_scores(pred, want, base, xyz, use):
    from summarize import hue_masks
    np = C.np
    result = {}
    masks = hue_masks(xyz)
    delta = C.lab(pred,'D65') - C.lab(want,'D65')
    for name, mask in masks.items():
        mask = mask & use
        if not mask.any():
            continue
        result[name] = dict(**score(pred[mask],want[mask],base[mask]),
            actual_minus_target_Lab_median=np.median(delta[mask],axis=0))
    return result


def main(style_id):
    C.admit('r2-' + style_id)
    C.numerical()
    C.sys.addaudithook(C.fence)
    np = C.np
    style = next(r for r in C.read(C.LOCAL/'styles.json') if r['id']==style_id)
    with np.load(C.LOCAL/'inputs.npz',allow_pickle=False) as z:
        v = dict(z)
    frames = C.read(C.LOCAL/'photos.json')
    metadata = C.read(R1/'inventory.json')[2]['metadata']
    model = C.camera_model(200,metadata['color_raw13'])
    want = same_scene_target(style,v['xyz'],v['base'])
    source_want = frozen_target(style,v['xyz'],v['base'],v['raw_codes'])
    assert np.isfinite(want).all()
    masks = dict(all55=v['bank']==0,lunch44=(v['bank']==0)&v['lunch'],
        morning11=(v['bank']==0)&~v['lunch'],strict96=(v['bank']==0)&v['strict96'],
        r1held=v['bank']==1,r1held_lunch=(v['bank']==1)&v['lunch'])
    k25_ids = [i for i,r in enumerate(frames) if r['g157_best']=='Kodachrome25' and r['group']=='lunch']
    high_ids = [i for i in k25_ids if frames[i]['g157_accepted']]
    masks['k25_24'] = (v['bank']==1)&np.isin(v['photo_id'],k25_ids)
    masks['k25_13'] = (v['bank']==1)&np.isin(v['photo_id'],high_ids)
    with np.load(style['old_groups']['photo_iso200'],allow_pickle=False) as z:
        old = dict(z)
    oldbase = old['base_new'] if 'base_new' in old else old['base']
    oldwant = same_scene_target(style,old['xyz'],oldbase)
    old_source_want = frozen_target(style,old['xyz'],oldbase,old['raw_codes'])
    target_replay = float(np.max(np.abs(old_source_want-old['want'])))
    assert target_replay<1e-8, (style['name'],'frozen target changed',target_replay)
    out = C.LOCAL/'results'/style_id
    out.mkdir(parents=True,exist_ok=True)
    arrays = dict(want=want,source_want=source_want)
    results = {}
    for position, record in style['variants'].items():
        assert C.sha(record['file'])==record['sha256']
        entry = Path(record['file']).read_bytes()
        continuous = C.predict(model,entry,v['x'])
        pred = np.rint(continuous)
        arrays[position+'_RGB'] = pred
        arrays[position+'_continuous'] = continuous
        scopes = {name:score(pred[use],want[use],v['base'][use]) for name,use in masks.items()}
        per_photo = []
        for i,frame in enumerate(frames):
            use = (v['bank']==0)&(v['photo_id']==i)
            per_photo.append(dict(id=frame['id'],group=frame['group'],**score(pred[use],want[use],v['base'][use])))
        old_pred = np.rint(C.predict(model,entry,old['x']))
        source_score = score(old_pred,old['want'],oldbase)
        for key in ('median','p95'):
            assert abs(source_score['de00'][key]-record['old_score']['de00'][key])<1e-8, (style['name'],position,key)
        same_old = score(old_pred,oldwant,oldbase)
        now = scopes['all55']['similarity_percent']
        before = same_old['similarity_percent']
        regions = region_scores(pred,want,v['base'],v['xyz'],masks['r1held'])
        kregions = region_scores(pred,want,v['base'],v['xyz'],masks['k25_24']) if style['name']=='Kodachrome25' else None
        results[position] = dict(record_sha256=record['sha256'],scores=scopes,per_photo=per_photo,
            source_holdout=record['old_score'],source_holdout_replayed=source_score,
            same_scene_holdout=same_old,change_pp=now-before,drop_more_than_10pp=now-before < -10,
            source_target_today=score(pred[masks['all55']],source_want[masks['all55']],v['base'][masks['all55']]),
            regions=regions,k25_regions=kregions)
    gap = {}
    for key in masks:
        gap[key] = results['full']['scores'][key]['similarity_percent']-results['Look']['scores'][key]['similarity_percent']
    per_photo_gap = [dict(id=a['id'],gap_pp=b['similarity_percent']-a['similarity_percent'])
                     for a,b in zip(results['Look']['per_photo'],results['full']['per_photo'])]
    old_actual = region_scores(v['observed'],want,v['base'],v['xyz'],masks['k25_24']) if style['name']=='Kodachrome25' else None
    np.savez_compressed(out/'predictions.npz',**arrays)
    result = dict(id=style_id,name=style['name'],planned=style['planned'],planned_placement=style['planned_placement'],
        planned_slot=style['planned_slot'],source_target_uses_04=style['source_target_uses_04'],
        results=results,full_minus_Look_pp=gap,
        Look_safe_on_all55=gap['all55']<=2,Look_safe_on_strict96=gap['strict96']<=2,
        Look_safe_on_r1held=gap['r1held']<=2,
        per_photo_gaps=per_photo_gap,old_g157_k25_actual_regions=old_actual,
        frozen_target_max_RGB_difference=target_replay,no_fit_or_tuning=True,created_utc=C.utc())
    C.dump(out/'result.json',result)
    placement = style['planned_placement'] or 'full'
    chosen = results[placement]
    print(style['name'],placement,'old/new/delta',round(chosen['same_scene_holdout']['similarity_percent'],2),
          round(chosen['scores']['all55']['similarity_percent'],2),round(chosen['change_pp'],2),
          'full-Look',round(gap['all55'],2),flush=True)


if __name__=='__main__':
    main(sys.argv[1])
