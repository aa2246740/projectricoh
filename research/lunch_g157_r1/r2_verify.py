"""Independent replay, source checks and evaluation-set integrity for R2."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r2_common import C,R1,FILM,PLANNED,same_scene_target,score,decision
import statistics


def main():
    C.admit('r2-verify')
    C.numerical()
    C.sys.addaudithook(C.fence)
    np=C.np
    frozen=C.read(C.LOCAL/'inputs.json')
    changed=[p for p,digest in frozen['files'].items() if C.sha(p)!=digest]
    assert not changed,'Source drift: '+repr(changed)
    blue=C.read(C.LOCAL/'blue.json')
    assert not blue['history_errors']
    changed=[p for p,digest in blue['protected_sources'].items() if C.sha(p)!=digest]
    assert not changed,'Library/source drift: '+repr(changed)
    originals=[]
    today=set()
    for row in C.read(R1/'inventory.json'):
        for pathkey,digestkey,statkey in (('path','raw_sha256','raw_stat'),('jpeg','jpeg_sha256','jpeg_stat')):
            p=Path(row[pathkey]);assert C.sha(p)==row[digestkey]
            assert [p.stat().st_size,p.stat().st_mtime_ns]==row[statkey]
            originals.append(dict(path=str(p),sha256=row[digestkey]))
        if row['group']!='previous_day':today.add(row['raw_sha256'])
    assert len(originals)==114 and len(today)==55 and C.sha(C.DAT)==C.DAT_SHA
    with np.load(C.LOCAL/'inputs.npz',allow_pickle=False) as z:v=dict(z)
    assert (v['bank']==0).sum()==5280
    assert len(np.unique(v['photo_id'][v['bank']==0]))==55
    assert np.array_equal(C.input_codes(v['raw_codes']),v['x'])
    metadata=C.read(R1/'inventory.json')[2]['metadata']
    model=C.camera_model(200,metadata['color_raw13'])
    stock=(C.LOCAL/'records/04_Std.record552').read_bytes()
    assert np.max(abs(C.predict(model,stock,v['x'])-v['base']))<1e-10
    source=C.ROOT/'research/bluecyan_r1/verify.py'
    function=next(n for n in C.ast.parse(source.read_text()).body if isinstance(n,C.ast.FunctionDef) and n.name=='predict_literal')
    scope=dict(np=np,struct=C.struct)
    exec(compile(C.ast.Module(body=[function],type_ignores=[]),str(source),'exec'),scope)
    literal=scope['predict_literal']
    D=C.module('r2_independent_record_reader',C.ROOT/'research/v39_g153/dat_format.py')
    selected=list(np.flatnonzero(v['bank']==0))
    for pid in np.unique(v['photo_id']):
        take=np.flatnonzero((v['bank']==1)&(v['photo_id']==pid))
        selected.extend(take[np.linspace(0,len(take)-1,min(24,len(take))).astype(int)])
    selected=np.asarray(selected)
    entries=[];maximum=0.;boundary=0
    from gxr_studio.lut.spaces import DISPLAY
    for style in C.read(C.LOCAL/'styles.json'):
        result=C.read(C.LOCAL/'results'/style['id']/'result.json')
        with np.load(C.LOCAL/'results'/style['id']/'predictions.npz',allow_pickle=False) as z:stored=dict(z)
        want=same_scene_target(style,v['xyz'],v['base'])
        assert np.max(abs(want-stored['want']))<1e-10
        if style['kind']=='style' and style['name']!='Acros official':
            target=style['target_definition']
            cube=C.Cube.read(C.ROOT/target['source'])
            checker=C.Target(cube,target['input'],target['output'])
            # An independent equivalent route: encode scene XYZ as sRGB,
            # then let the declared Target perform its display-input conversion.
            srgb=C.xyz_to_encoded(v['xyz'][selected],'srgb')*255
            independent=checker.render(srgb,v['xyz'][selected])
            assert np.max(abs(independent-want[selected]))<1e-7
        for position,rec in style['variants'].items():
            assert Path(rec['source']).is_relative_to(FILM),'Candidate source outside film_looks_r2'
            assert C.sha(rec['source'])==rec['sha256']==C.sha(rec['file'])
            b=Path(rec['file']).read_bytes()
            assert D.refresh_entry(b)==b
            pred=literal(model,b,v['x'][selected])
            diff=float(np.max(abs(pred-stored[position+'_continuous'][selected])))
            maximum=max(maximum,diff);assert diff<1e-8
            rounded=np.rint(pred);saved=stored[position+'_RGB'][selected]
            mismatch=rounded!=saved
            if mismatch.any():
                distance=np.abs((pred-np.floor(pred))-.5)
                assert np.all(distance[mismatch]<1e-9)
                boundary+=int(mismatch.sum())
            use=v['bank']==0
            actual=score(stored[position+'_RGB'][use],want[use],v['base'][use])
            expected=result['results'][position]['scores']['all55']
            assert abs(actual['similarity_percent']-expected['similarity_percent'])<1e-10
            for k in ('median','p95'):
                assert abs(actual['de00'][k]-expected['de00'][k])<1e-10
            entries.append(dict(name=style['name'],position=position,sha256=rec['sha256'],
                                points=len(selected),literal_max_RGB=diff))
    assert len(entries)==54
    summary=C.read(C.LOCAL/'summary.json')
    assert len(summary['planned_table'])==13
    expected_mean=statistics.mean(r['change_pp'] for r in summary['planned_table'])
    assert abs(expected_mean-summary['mean_change_pp'])<1e-12
    k=C.read(C.LOCAL/'results/kodachrome25/result.json')
    # R1's actual-to-target gap is reproduced on the same 24 photos and masks.
    previous=C.read(R1/'summary.json')
    old=next(r for r in previous['scopes']['lunch']['recipes'] if r['name']=='Kodachrome25')
    for region in ('neutral','middle','yellow','cyan'):
        a=old['style_regions']['r2'][region]
        b=k['old_g157_k25_actual_regions'][region]
        assert abs(a['actual']['median']-b['de00']['median'])<1e-10
        assert np.max(abs(np.asarray(a['actual_minus_target_Lab_median'])-b['actual_minus_target_Lab_median']))<1e-10
    candidates=C.read(C.LOCAL/'library-blue-candidates.json')
    available=[r for r in candidates if r['sha256'] not in today]
    label_counts={}
    for row in available:
        contents={r['content'] for r in row['labels_from_either_pair_member']}
        for key in contents:label_counts[key]=label_counts.get(key,0)+1
    availability=dict(labelled_blue_pairs=len(candidates),overlap_with_today=len(candidates)-len(available),
        eligible_before_identity_review=len(available),ISO200=sum(r['iso']==200 for r in available),
        fixed_WB_ISO200=sum(r['iso']==200 and r['wb_mode'] in ('Manual','Daylight') for r in available),
        identity_unknown=sum(r['recipe']=='unknown' for r in available),content_labels=label_counts,
        current_55_are_never_training_material=True)
    oldphotos=C.read(FILM/'inputs/mount-a12/photos.json')
    oldhashes={r['sha256'] for r in oldphotos if r.get('sha256')}
    assert not (oldhashes&today),'Today duplicates a previous input photo'
    C.dump('originals-after.json',originals)
    C.dump('library-availability.json',availability)
    C.dump('verification.json',dict(status='PASS',original_photo_files=114,DAT_unchanged=True,
        protected_sources=len(frozen['files']),protected_library_sources=len(blue['protected_sources']),
        records=entries,literal_points=sum(r['points'] for r in entries),
        literal_max_RGB=maximum,half_code_boundary_differences=boundary,
        source_holdout_replayed_for_all_records=True,original_R1_regional_gaps_reproduced=True,
        today_overlap_with_previous_inputs=0,library_availability=availability,
        no_fit_or_tuning=True,all_nice15=True,all_isolated=True,created_utc=C.utc()))
    decision('verify','复核54条记录与原始文件，重现上一轮K25区域差距',
             '新记录只做前向预测，独立方程和冻结旧留出用于查接线错误',
             'local/r2/verification.json','PASS; 54 records; 114 originals unchanged')
    print('VERIFY PASS',len(entries),'records;',sum(r['points'] for r in entries),
          'literal points; max RGB',maximum,'library',availability,flush=True)


if __name__=='__main__':main()
