"""Uniform-patch quantization, neutral pass and field-unit sensitivity.

Uniform-patch rounding is explicitly not a simulation of actual JPEG pixels.
No retraining or held-out selection occurs in this diagnostic.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pipeline import *
replay=rt.module('second_pass_diagnostic_replay',rt.HERE/'verify.py')
first_from_codes,body_from_codes,native_codes=replay.first_from_codes,replay.body_from_codes,replay.native_codes
import copy
import json


def roundtrip(m,rgb):
    z=np.rint(np.clip(rgb@B601.T+[0,128,128],0,255))
    return np.clip(m.mm.rgb_from_ycc(z[:,0],z[:,1]-128+1j*(z[:,2]-128)),0,255)


def main():
    m=rt.model();rows=[];neutral=[];cache={};predictions={}
    for path in sorted((rt.LOCAL/'fits').glob('*/*/*.json')):
        doc=rt.read(path);slot,fold=doc['slot'],doc['fold'];key=(slot,fold)
        if key not in cache:
            d=rt.arrays(rt.LOCAL/f'data/{slot}/{fold}.npz');meta=rt.read(rt.LOCAL/f'data/{slot}/{fold}.json')
            d['current']=meta['current'];cache[key]=d
        d=cache[key];a=rt.arrays(path.with_suffix('.npz'));held=a['held']
        first=first_from_codes(m,d,doc['packed']['first']);c=doc['packed']['body']
        variants={'uniform_YCC8_roundtrip':roundtrip(m,body_from_codes(m,roundtrip(m,first),c))}
        for unit in (1.,.25,.0625):
            cc=copy.deepcopy(c)
            for block,field in [('offsets','offsets_8bit_units'),('tint','c004')]:
                if block in doc['body_blocks']:
                    raw=np.array(doc['theta_continuous'])[slice(*doc['body_blocks'][block])]
                    cc[field]=np.rint(raw/unit).astype(int)
            cc['offset_unit']=cc['tint_unit']=unit
            if np.max(abs(np.asarray(cc['c004'])))<=127:
                variants[f'body_offset_tint_unit_{unit:g}']=body_from_codes(m,first,cc)
        if c['c120_axis']=='C':
            for radius in (128.,96.):
                cc=copy.deepcopy(c);cc['c120_radius']=radius
                variants[f'fixed_codes_C_radius_{radius:g}']=body_from_codes(m,first,cc)
        for name,pred in variants.items():
            error=m.fs.delta_e00(m.fs.lab_from_codes(pred),d['target'])
            index=(slot,doc['route'],name)
            predictions.setdefault(index,[]).append((fold,error[held],d['baseline'][held]))
        if doc['mode']=='fixed':
            P=Body(m,doc['tier'],doc['order'],native_codes())
            pred=P.predict(np.zeros(P.np),d['first_published'],True)
            error=m.fs.delta_e00(m.fs.lab_from_codes(pred),d['target'])
            neutral.append(dict(slot=slot,fold=fold,order=doc['order'],tier=doc['tier'],score=old.score(error[held],d['baseline'][held])))
    for (slot,route,name),values in predictions.items():
        for scheme in ('page','hue','full'):
            selected=[v for v in values if v[0].startswith(scheme)]
            if not selected:continue
            error=np.concatenate([v[1] for v in selected]);base=np.concatenate([v[2] for v in selected])
            rows.append(dict(slot=slot,route=route,variant=name,scheme=scheme,score=old.score(error,base),
                             prediction_label='电脑预测',refitted=False,uniform_pixel_assumption=name.startswith('uniform')))
    target_diagnostics=[]
    for slot in SLOTS:
        d=cache[slot,'full'];use=d['score_mask'];target=d['target'][use]
        xyz=m.fs.lab_to_xyz(target,m.fs.D65)
        raw=m.fs.linear_to_srgb(xyz@np.linalg.inv(m.fs.M709).T)*255
        projected=np.clip(raw,0,255)
        err=m.fs.delta_e00(m.fs.lab_from_codes(projected),target)
        first=d['first_published'][use]
        unique,inverse,counts=np.unique(np.round(first,8),axis=0,return_inverse=True,return_counts=True)
        collisions=[]
        for index in np.flatnonzero(counts>1):
            take=np.flatnonzero(inverse==index);maximum=0.
            for i in take:maximum=max(maximum,float(np.max(m.fs.delta_e00(np.broadcast_to(target[i],target[take].shape),target[take]))))
            collisions.append(dict(indices=take,max_target_de00=maximum))
        target_diagnostics.append(dict(slot=slot,n=len(target),
           target_rgb_outside_gamut=int(np.any((raw<-.0001)|(raw>255.0001),axis=1).sum()),
           pointwise_target_projection=old.score(err,d['baseline'][use]),
           published_first_boundary_points=int(np.any((first<=1e-8)|(first>=255-1e-8),axis=1).sum()),
           same_rgb_groups=collisions,
           caveat='target-aware pointwise projection, no generalization score or bridge proof; rounded-to-1e-8 equality is a model diagnostic'))
    rt.dump('diagnostics.json',dict(rows=rows,neutral=neutral,target_diagnostics=target_diagnostics,
      notes=['field-unit alternatives repack continuous offset/tint only; other final integer parameters fixed',
             'C radius alternatives keep all integer codes fixed and do not establish optimized C-axis ceilings',
             'YCC8 uniform-patch calculation rounds means as if each patch were spatially uniform; not actual adjacent pixels']))
    rt.finish('diagnostics');print(json.dumps(dict(rows=len(rows),neutral_fits=len(neutral))),flush=True)


if __name__=='__main__':main()
