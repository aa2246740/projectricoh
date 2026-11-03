"""Recompute the earlier GR IV 90-94 percent references from saved predictions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,ROOT,LOCAL

def main():
    folder=ROOT/'research/gr4_lut_ceiling/local/lut'
    body=rt.read(folder/'body_summary.json')
    rows=[]
    for slot in ('01','02'):
        for scheme in ('patch','hue','screen_to_physical'):
            for size in (17,33):
                path=folder/f'body_{slot}_{scheme}_pixel{size}.npz'
                with np.load(path,allow_pickle=False) as z:
                    prediction,target,baseline,error=[z[k].copy() for k in ('prediction','target','baseline','error')]
                actual=rt.delta_e00(rt.lab_from_codes(prediction),target)
                assert np.max(abs(actual-error))<1e-9
                similarity=1-float(np.median(actual))/float(np.median(baseline))
                original=next(r for r in body if r['slot']==slot and r['scheme']==scheme and r['route']=='pixel_LUT'+str(size))
                assert abs(similarity-original['similarity_median'])<1e-12
                rows.append(dict(label='电脑预测，既有预测数组独立复核',slot=slot,scheme=scheme,cube=size,
                    similarity_percent=100*similarity,de00=rt.stats(actual),baseline_de00=rt.stats(baseline),
                    source=str(path.relative_to(ROOT)),sha256=rt.sha(path),
                    target_scope='relative GR IV bridge proxy; not same physical materials captured by both cameras'))
    native=[]
    for slot in ('01','02'):
        for size in (17,33):
            path=folder/f'native1477_{slot}_{size}.npz'
            with np.load(path,allow_pickle=False) as z:
                prediction,target,baseline,error=[z[k].copy() for k in ('prediction','target','baseline','error')]
            actual=rt.delta_e00(rt.lab_from_codes(prediction),target)
            assert np.max(abs(actual-error))<1e-9
            native.append(dict(slot=slot,cube=size,label='电脑预测，既有原生标准JPEG留出独立复核',
                similarity_percent=100*(1-float(np.median(actual))/float(np.median(baseline))),
                de00=rt.stats(actual),baseline_de00=rt.stats(baseline),
                source=str(path.relative_to(ROOT)),sha256=rt.sha(path),
                target_is_proxy_not_same_scene_GR_IV=True))
    rt.dump(LOCAL/'legacy_gr_evidence.json',dict(
        bridge=rt.read(ROOT/'research/gr4_lut_ceiling/local/bridge/matrices.json'),
        native_renderer=rt.read(ROOT/'research/gr4_lut_ceiling/local/bridge/native.json')))
    rt.dump('legacy_gr_checks.json',dict(body_LUT=rows,native_standard=native,
        bridge_error_identifiable=False,
        warning='Around 0.5 DE00 describes renderer/interpolation terms, not measured cross-camera spectral error.'))
    rt.finish('legacy_checks')
    print('Recomputed',len(rows),'earlier LUT references and',len(native),'native-JPEG controls',flush=True)

if __name__=='__main__':main()
