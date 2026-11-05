"""Read-only library census and fixed native-model residual diagnostics. No fitting."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r2_common import C, R1, decision
from collections import Counter
import sqlite3


def main():
    C.admit('r2-blue')
    C.numerical()
    C.sys.addaudithook(C.fence)
    np=C.np
    from summarize import hue_masks
    protected={}
    def read(p):
        p=Path(p);protected[str(p)]=C.sha(p);return C.read(p)
    dbpath=C.ROOT/'research/data_index/local/index.sqlite'
    protected[str(dbpath)]=C.sha(dbpath)
    snapshot=C.LOCAL/'library-index.sqlite'
    snapshot.write_bytes(dbpath.read_bytes())
    db=sqlite3.connect('file:'+str(snapshot)+'?mode=ro&immutable=1',uri=True)
    db.row_factory=sqlite3.Row
    sql="""select distinct p.sha256,p.iso,p.shutter_s,p.wb_mode,p.setting,p.recipe,p.dat,p.exif_time,
                  p.unit_conflict
           from photos p join pairs q on q.dng_sha256=p.sha256
           join labels l on l.sha256 in (q.dng_sha256,q.jpg_sha256)
           join json_each(l.subjects) j where p.unit='MOUNT' and j.value='blue_object'"""
    blue=[dict(r) for r in db.execute(sql)]
    allpairs=db.execute("select count(distinct q.dng_sha256) from pairs q join photos p on p.sha256=q.dng_sha256 where p.unit='MOUNT'").fetchone()[0]
    candidate_refs=[]
    for row in blue:
        refs=[dict(r) for r in db.execute('select path,source from paths where sha256=?',(row['sha256'],))]
        digests={row['sha256']}
        digests.update(r[0] for r in db.execute('select jpg_sha256 from pairs where dng_sha256=?',(row['sha256'],)))
        evidence=[];conflicts=[];labels=[]
        for digest in sorted(digests):
            evidence += [dict(r) for r in db.execute('select field,value,source from evidence where sha256=?',(digest,))]
            conflicts += [dict(r) for r in db.execute('select field,value_a,value_b from conflicts where sha256=?',(digest,))]
            labels += [dict(r) for r in db.execute('select content,environment,subjects,confidence,model from labels where sha256=?',(digest,))]
        candidate_refs.append(dict(**row,paths=refs,evidence=evidence,conflicts=conflicts,labels_from_either_pair_member=labels))
    census=dict(MOUNT_paired_DNGs=allpairs,blue_labelled_paired_DNGs=len(blue),
        ISO=dict(Counter(str(r['iso']) for r in blue)),WB=dict(Counter(str(r['wb_mode']) for r in blue)),
        recipe=dict(Counter(str(r['recipe']) for r in blue)),
        labelled_blue_ISO200=sum(r['iso']==200 for r in blue),
        labelled_blue_manual_WB_ISO200=sum(r['iso']==200 and str(r['wb_mode']).lower() not in ('0','auto','unknown','none') for r in blue),
        with_conflicting_evidence=sum(bool(r['conflicts']) for r in candidate_refs),
        subjects_are_existing_labels_not_new_semantic_ground_truth=True)
    C.dump('library-blue-candidates.json',candidate_refs)
    # Compare the 17 already matched same-scene exposures, without re-identifying them.
    summary=read(R1/'summary.json')
    byid={r['id']:r for r in summary['rows']}
    poster=[]
    bank=read(R1/'bank.json')['records']
    for pid in summary['final_scene']['group_ids']:
        row=byid[pid]
        p=R1/'frames'/pid/'samples.npz';protected[str(p)]=C.sha(p)
        with np.load(p,allow_pickle=False) as z:v=dict(z)
        held=v['held'];x=v['conditioned'][held];obs=v['observed'][held]
        mask=hue_masks(v['xyz'][held])['blue']
        j=row['best_index'];pred=v['predictions'][j,held]
        model=C.camera_model(200,row['metadata']['color_raw13'])
        b=Path(bank[j]['record']).read_bytes()
        pre=model.pre(b,x)
        y,ci=C.mm.MatrixRow.from_bytes(b[216:244]).apply(pre)
        lab_delta=C.lab(obs)-C.lab(pred)
        ycc_delta=(obs-pred)@np.array([[.299,-.168736,.5],[.587,-.331264,-.418688],[.114,.5,-.081312]])
        record=dict(id=pid,name=row['best'],accepted=row['accepted'],blue_points=int(mask.sum()),
            blue_de00=C.stats(C.de(pred[mask],obs[mask])),
            signed_Lab=np.median(lab_delta[mask],axis=0),signed_YCbCr=np.median(ycc_delta[mask],axis=0),
            input_hue_quantiles=np.percentile(np.angle(ci[mask],deg=True)%360,[5,50,95]),
            input_chroma_quantiles=np.percentile(abs(ci[mask]),[5,50,95]))
        if pid=='R8052093':
            stock=Path(next(r['record'] for r in bank if r['name']=='04 Std')).read_bytes()
            controls={}
            for field,segments in dict(curves=((20,115),(379,445)),matrix=((216,244),),C080=((115,211),)).items():
                q=bytearray(b)
                for start,stop in segments:q[start:stop]=stock[start:stop]
                if field=='curves':q[1]=(q[1]&~4)|(stock[1]&4)
                prediction=C.predict(model,bytes(q),x)
                controls[field]=dict(all=C.stats(C.de(prediction,obs)),blue=C.stats(C.de(prediction[mask],obs[mask])))
            source_spec=read(C.ROOT/'research/hue_ring/local/ring_model_v2.json')
            native_spec=model.engine.table.model
            transferred={k:native_spec.get(k)==source_spec.get(k) for k in ('kernel','k_coupling','gain','gain_per_sector')}
            frozen=read(C.ROOT/'research/model_c040_r1/local/physical/ring-mount-a12-200.json')
            assert np.array_equal(model.engine.table.nodes,np.asarray(frozen['nodes_unwrapped_deg']))
            record.update(fixed_04_component_controls=controls,
                C040_nodes_already_equal_to_model_c040_native=True,
                residual_C080_model_parameters_still_equal_to_50mm=transferred,
                already_corrected_geometry_not_a_new_fix=True)
        poster.append(record)
    # Frozen historical response identities, never reclassified on these residuals.
    history_root=C.ROOT/'research/bluecyan_r1/local'
    identities=read(history_root/'history/identities.json')
    mount=[r for r in identities if r.get('identity',{}).get('accepted') and r['metadata']['unit']=='mount-a12']
    history=[];flat={};errors=[]
    for row in mount:
        if row['metadata']['iso']!=200:continue
        labels=row['identity']['record']['labels']
        setting=next((s for s in ('04','05','06') if s in labels),None)
        if setting is None:continue
        try:
            path=Path(row['path'])
            allowed=path.is_relative_to(C.ROOT) or path.is_relative_to('/Users/wu/Pictures/GXR Studio')
            assert allowed,'Unknown library location'
            d=C.Dng(path);assert d.sha256==row['raw_sha256']
            protected[str(path)]=d.sha256
            colour=C.scene_colour(d)
            sample=Path(row['samples_file']);sample=sample if sample.is_absolute() else history_root/sample
            protected[str(sample)]=C.sha(sample)
            with np.load(sample,allow_pickle=False) as z:v=dict(z)
            held=v['cells'].sum(1)%2==1
            raw,obs=v['raw_codes'][held],v['observed'][held]
            xyz=colour.xyz(raw);mask=hue_masks(xyz)['blue']
            rec=row['identity']['record'];p=Path(rec['record']);p=p if p.is_absolute() else history_root/p
            protected[str(p)]=C.sha(p)
            assert C.sha(p)==rec['sha256']
            model=C.camera_model(200,row['metadata']['color_raw13'])
            pred=C.predict(model,p.read_bytes(),C.input_codes(raw))
            value=C.de(pred[mask],obs[mask])
            pre=model.pre(p.read_bytes(),C.input_codes(raw))
            y,ci=C.mm.MatrixRow.from_bytes(p.read_bytes()[216:244]).apply(pre)
            out=dict(path=str(path),raw_sha256=d.sha256,setting=setting,day=row['day'],
                     blue_points=int(mask.sum()),blue_de00=C.stats(value),
                     wb_mode=row['metadata'].get('wb_mode'),identity_frozen=True,
                     record_sha256=rec['sha256'],
                     input_hue_quantiles=np.percentile(np.angle(ci[mask],deg=True)%360,[5,50,95]) if mask.any() else None,
                     input_chroma_quantiles=np.percentile(abs(ci[mask]),[5,50,95]) if mask.any() else None)
            history.append(out)
            flat.setdefault(setting,[]).extend(value)
            d.release()
        except Exception as e:
            errors.append(dict(path=row['path'],error=repr(e)))
    hist_summary={setting:dict(exposures=sum(r['setting']==setting for r in history),
        blue_exposures=sum(r['setting']==setting and r['blue_points']>0 for r in history),
        blue_de00=C.stats(v)) for setting,v in flat.items()}
    C.dump('library-native-blue-replay.json',dict(photos=history,errors=errors,groups=hist_summary,
        region='same input-scene blue Lab range as R1; odd spatial halves; ISO200 only'))
    # Existing controlled data: report what it actually perturbs, not a proposed new fit.
    points=read(C.ROOT/'research/model_c040_r1/local/physical/probe-points.json')
    probe_score=read(C.ROOT/'research/model_c040_r1/local/physical/probe-scores.json')
    probe_counts={}
    for probe in ('probe2','probe3'):
        r=[p for p in points if p['probe']==probe and p['ROI']=='0.5']
        probe_counts[probe]=dict(central_points=len(r),gray=dict(Counter(str(p['gray']) for p in r)),
            labels=dict(Counter(p['label'] for p in r)),patches=len({p['patch'] for p in r}))
    expected=read(C.ROOT/'research/probe_pack_r3/local/expected.json')['M']
    A=bytes.fromhex(expected['A']['entry_hex'])
    probe_changes={}
    for label,row in expected.items():
        b=bytes.fromhex(row['entry_hex'])
        probe_changes[label]={name:sum(x!=y for x,y in zip(b[start:stop],A[start:stop])) for name,start,stop in
            (('C080',115,211),('matrix',216,272),('curve_G',82,115),('curve_R',379,412),('curve_B',412,445))}
    previous_blue=read(C.ROOT/'research/model_c040_r1/local/blue-object.json')
    noon=read(C.ROOT/'research/model_c040_r1/local/physical/noon-scores.json')
    C.dump('blue.json',dict(census=census,poster=poster,history=hist_summary,history_errors=errors,
        previously_accepted_mount=len(mount),previously_accepted_mount_ISO200=sum(r['metadata']['iso']==200 for r in mount),
        controlled_probe_counts=probe_counts,controlled_probe_scores=probe_score['scores'],
        probe3_changed_components=probe_changes,
        prior_blue_object=previous_blue,noon_scores=noon,
        attribution='Current native C040 geometry is already applied. A unique split between C040 empirical residual, transferred C080 kernel/gain, input map and spatial ISP is not identified by this photograph.',
        no_model_fit_or_parameter_sweep=True,no_new_capture_requested=True,
        protected_sources=protected,created_utc=C.utc()))
    decision('blue','先盘点现库，再重放已认定 ISO200 的 04/05/06 蓝色域',
             '照片标签不等于配方真值，单张残差不能唯一拆分 C040/C080',
             'local/r2/blue.json; local/r2/library-native-blue-replay.json',
             f'{len(blue)} labelled blue pairs; {len(history)} old ISO200 exposures replayed')
    print('BLUE CENSUS',census,flush=True)
    print('BLUE HISTORY',hist_summary,'errors',len(errors),flush=True)
    print('PROBE COUNTS',probe_counts,'CHANGED COMPONENTS',probe_changes,flush=True)


if __name__=='__main__':main()
