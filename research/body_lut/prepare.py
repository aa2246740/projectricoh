"""Build measured 04 -> same-frame DNG targets. Never calls capture/firmware tools."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, LOCAL, guard, inp, read, dump, load, sha
import numpy as np
from PIL import Image

SLOTS = ('01', '02', '05', '06')


class Provenance:
    def add(self, p):
        return inp(p)


def modules():
    cm = load('closed_common', 'research/closed_loop/common.py')
    # Imported modules retain their own frozen helper paths. No source helper is run as a CLI.
    sys.modules['common'] = cm
    mm = load('closed_model', 'research/closed_loop/model.py')
    tt = load('closed_targets', 'research/closed_loop/targets.py')
    for p in (ROOT/'research/closed_loop/local/vendor').rglob('*.py'):
        inp(p)
    return cm, mm, tt


def rgb_to_ycc(rgb):
    rgb = np.asarray(rgb, float)
    y = rgb @ np.array([.299, .587, .114])
    return np.stack([y, 128+(rgb[...,2]-y)/1.772,
                     128+(rgb[...,0]-y)/1.402], axis=-1)


def ycc_to_rgb(ycc):
    q = np.asarray(ycc, float)
    y, cb, cr = q[...,0], q[...,1]-128, q[...,2]-128
    return np.stack([y+1.402*cr, y-.3441362862*cb-.7141362862*cr,
                     y+1.772*cb], axis=-1)


def main():
    guard()
    cm, mm, tt = modules()
    p = Provenance()
    table = ROOT/'artifacts/stage2j-packages/tables-v4r3-noprobe/DEEPTBL0.DAT'
    engine = mm.Engine(table=table, provenance=p)
    targets = tt.Targets(engine, p)
    dsmod = cm.helper('dng')
    ar = cm.helper('ar')
    # Reuse verified geometry/patch identity; all CFA samples below are recomputed from original DNGs.
    ring = read('research/closed_loop/local/dry_ring_measurement.json')
    phys = read('research/closed_loop/local/dry_2e_measurement.json')
    frames = [f for src in (ring, phys) for f in src['frames'] if f['slot']=='04']
    for stem in ('R8051171','R8051174'):
        old = read(f'research/matrix_test_onbody/local/{stem}.json')
        folder = f'captures/a12-50/2026-10-20/stage2j-matrixtest-screen/{stem}'
        meta = ar.read_meta(ROOT/(folder+'.JPG'), ROOT/(folder+'.DNG'), None)
        frames.append({'id':stem, 'slot':'04', 'set':'screen-matrix', 'chart':'hue-ring',
            'jpeg':folder+'.JPG', 'dng':folder+'.DNG', 'meta':meta,
            'geometry':old['geometry'], 'patches':[{'label':str(q['id']), 'name':
                ar.load_layout()['patches'][i]['name'], 'gray':i>=144,
                'rgb':q['rgb_trim'], 'roi':q['inner_rect'], 'flags':[]}
                for i,q in enumerate(old['samples']['30'])]})
    allrows, metas = [], []
    for f in frames:
        jp, dp = inp(f['jpeg']), inp(f['dng'])
        if f.get('hashes'):
            assert sha(jp)==f['hashes']['JPEG'] and sha(dp)==f['hashes']['DNG']
        with Image.open(jp) as im:
            rgb = np.asarray(im.convert('RGB'))
        ds = dsmod.DngScene(dp, jp, jpeg_rgb=rgb, verify=True)
        assert ds.verify and ds.verify['ok'], (f['id'], ds.verify)
        own_raw, own_xyz, patches = [], [], []
        pair_samples = []
        for q in f['patches']:
            roi = [int(v) for v in q['roi']]
            raw = ds.stats({'rect':roi})
            own_raw.append(raw['cam'])
            own_xyz.append(ds.xyz(raw['cam'], ds.white_as_shot)[0])
            patches.append({**q,'raw':raw})
            # Real adjacent horizontal pairs, sampled inside the actual photograph's patch ROI.
            x0,y0,x1,y1=roi
            x0 += x0 % 2
            x1 -= x1 % 2
            block = rgb[y0:y1, x0:x1].reshape(-1, 2, 3)
            pair_samples.append(block[np.linspace(0,len(block)-1,24,dtype=int)])
        f.update({'patches':patches, 'raw_cam':np.asarray(own_raw),
            'raw_wb':np.asarray(own_raw)/np.asarray(f['meta']['asn']),
            'xyz_camera':np.asarray(own_xyz)})
        obs = np.asarray(f['rgb'] if 'rgb' in f else [q['rgb'] for q in patches])
        # A 04 frame is its own baseline: no cross-frame raw scaling enters the targets.
        xx,bad = engine.invert04(obs, f['raw_wb'])
        stock = engine.predict('04', xx)
        outputs, predictions, definitions = {}, {}, {}
        for slot in SLOTS:
            outputs[slot], definitions[slot] = targets.render({**f,'slot':slot},f,xx,stock)
            predictions[slot] = engine.predict(slot,xx)
        scene_lab = engine.fs.xyz_to_lab(np.maximum(f['xyz_camera'],0))
        for i,q in enumerate(patches):
            allrows.append({'frame':f['id'],'domain':'physical' if f['chart']=='physical' else 'screen',
                'group':('physical:' if f['chart']=='physical' else 'screen:')+q['label'],
                'label':q['label'], 'name':q['name'], 'gray':q['gray'],
                'rgb':obs[i], 'ycc':np.clip(np.floor(rgb_to_ycc(obs[i])+.5),0,255),
                'targets':{s:outputs[s][i] for s in SLOTS},
                'isp_rgb':{s:predictions[s][i] for s in SLOTS},
                'dng_hue':float(np.degrees(np.arctan2(scene_lab[i,2],scene_lab[i,1]))%360),
                'raw_clip':q['raw']['clip_frac'], 'jpeg_clip':float(np.mean(np.any(
                    (pair_samples[i]<=2)|(pair_samples[i]>=253),axis=-1))),
                'model_inverse_bad':bool(bad[i]), 'flags':q.get('flags',[]),
                'pairs_rgb':pair_samples[i]})
        metas.append({'id':f['id'],'jpeg':str(jp.relative_to(ROOT)),'dng':str(dp.relative_to(ROOT)),
            'jpeg_sha256':sha(jp),'dng_sha256':sha(dp),'n':len(patches),
            'iso':f['meta'].get('iso'),'asn':f['meta'].get('asn'),
            'registration':ds.verify,'targets':definitions,'04_inverse_bad':int(np.sum(bad))})
        print('prepared', f['id'], len(patches), flush=True)
    dump('dataset.json', {'schema':'body-lut-dataset/1','rows':allrows,'frames':metas,
        'source':'actual 04 JPEG patch statistics; CFA and XYZ recomputed from same-frame DNG',
        'table':str(table.relative_to(ROOT)),'table_sha256':sha(table),
        'input_encoding':'JFIF full-range YCbCr, round-half-up 8-bit; not yet camera RAM encoding',
        'heldout_group':'all repeated observations of the same screen/physical patch leave together',
        'reference_scope':'01/02 GR relative surrogate; 05/06 official LUT chain; no original-camera likeness claim'})


if __name__=='__main__':
    main()
