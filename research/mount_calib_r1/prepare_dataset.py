"""Inject the operator report and freeze targets independently of Mount fitting."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np, s, calibrate
import copy
import json
from scipy.spatial import cKDTree


def inject():
    if (rt.LOCAL/'frames.json').exists():
        data = rt.read('frames.json')
        assert data['correction_defaults_are_assumed'] and all(f['aperture_f'] == 2 for f in data['frames'].values())
        return data
    session = rt.load('session_runtime', 'research/chart_session_20261024/session_runtime.py')
    session.HERE, session.LOCAL = rt.HERE, rt.LOCAL
    session.audit = rt.audit
    inject = rt.load('mount_inject', 'research/chart_session_20261024/inject_mount_report.py')
    report = inject.template()
    report['capture'].update(actual_aperture_f=2., corrections={
        'peripheral_illumination': 0, 'red_blue_shading': {'TL':[0,0],'TR':[0,0],'BL':[0,0],'BR':[0,0]}, 'distortion': 0})
    report['note'] = 'User confirmed 35mm f/2 M lens at f/2. Correction values are ASSUMED unchanged factory defaults because MakerNote fields could not be identified; they were not reported by the user.'
    report['correction_value_source'] = 'assumed_factory_defaults_not_observed'
    rt.dump('operator_report.json', report)
    sys.argv = ['inject_mount_report.py', '--report', str(rt.LOCAL/'operator_report.json'),
        '--frames', str(rt.EXCHANGE/'frames.json'), '--output', str(rt.LOCAL/'frames.json')]
    inject.main()
    data = rt.read('frames.json')
    data['unknown_metadata_is_not_imputed'] = False
    data['correction_defaults_are_assumed'] = True
    for f in data['frames'].values():
        f['corrections_source'] = 'assumed_factory_defaults_not_observed'
        f['lens_note'] = 'User confirmed 35mm f/2 M lens, actual f/2; brand and serial unknown.'
    rt.dump('frames.json', data)
    return data


def frozen_targets(m):
    target_mod = rt.load('mount_targets', 'research/closed_loop/targets.py')
    class Provenance:
        def add(self, p):
            return s.source(p)
    t = target_mod.Targets(m.base, Provenance())
    bw = s.source(rt.ROOT/'research/chart_session_20261024/local/extraction/bw_reference.npz')
    with np.load(bw, allow_pickle=False) as z:
        t.bw_tree = cKDTree(np.log2(np.maximum(z['x'], 1)))
        t.bw_j, t.bw_frame = z['j'].copy(), z['frame'].copy()
    sys.path.insert(0,str(rt.ROOT/'research/chart_v2'))
    sys.path.insert(0,str(rt.ROOT/'research/lut_convert'))
    scoring = rt.load('mount_scoring', 'research/chart_v2/analyzer_scoring.py')
    cube_mod = rt.load('mount_cube', 'research/lut_convert/cube.py')
    spaces = rt.load('mount_spaces', 'research/lut_convert/spaces.py')
    pan_mod = rt.load('mount_panasonic', 'research/huzi_luts/panasonic.py')
    pm = s.read(rt.ROOT/'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard/manifest.json')
    ent = next(e for e in pm['luts'] if Path(e['path']).stem == 'S1RIIS2V')
    pp = rt.ROOT/'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard'/ent['path']
    assert s.digest(pp) == ent['sha256']
    inv = pan_mod.StandardInverse(cube_mod.Cube.read(s.source(pp)))
    cubes = {slot: cube_mod.Cube.read(s.source(rt.ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'/name))
        for slot,name in (('07','Leica Chrome.cube'),('08','Leica VIVID.cube'))}
    camera_mod = rt.load('mount_lut_camera', 'research/lut_convert/camera.py')
    # Only Camera.xyz is needed; constructing Camera would install another output/cache owner.
    from types import SimpleNamespace
    anchor = s.read(rt.ROOT/'research/color_fit_v2/05_classic_chrome/round4/local/fit_v4_noT1.json')['anchor']
    camera = SimpleNamespace(anchor=anchor)
    rows50 = [json.loads(l) for l in s.source(rt.ROOT/'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/50mm/patches.jsonl').read_text().splitlines()]
    out = []
    info = {}
    m50 = rt.UnitModel('50mm', iso=200)
    for page in range(1,7):
        stem = f'R805{1269+page}'
        frame = s.read(rt.ROOT/f'research/chart_session_20261024/local/analysis-final/frames/{stem}.json')
        patchmap = {r['patch_id']:r for r in rows50 if r['frame'] == stem}
        for p in frame['patches']:
            r = patchmap[p['patch_id']]
            p['jpeg_rgb'],p['raw_rgb'] = r['jpeg_rgb'],r['raw_rgb']
            p['raw_wb'] = (np.array(r['raw_rgb'])*np.array(frame['meta']['asn'])**-1).tolist()
        ff = scoring.as_measure_frame(frame)
        jpg, raw = ff['rgb'], ff['raw_wb']
        x, bad = m50.inverse04(jpg, raw)
        # Scene targets use the independent 50mm RAW and its recorded DNG matrix.
        M = np.linalg.lstsq(ff['raw_cam'], ff['xyz_camera'], rcond=None)[0].T
        xyz = camera_mod.Camera.xyz(camera, raw*4095, np.array(frame['meta']['asn']), M)
        vlog = spaces.xyz_to_encoded(xyz, 'vlog')
        pan, inverse_residual = inv.invert(vlog)
        for slot in ('01','02','03','05','06','07','08'):
            if slot in cubes:
                rgb = np.clip(.3*pan*255+.7*cubes[slot].apply(pan)*255,0,255)
                lab = m.fs.lab_from_codes(rgb)
                meta = {'kind':'same scene Panasonic S1RII inverse + original Huzi LUT, 70%',
                    'panasonic_inverse_residual': inverse_residual.tolist(), 'unsupported_patches': []}
            else:
                f = {**ff, 'slot':slot}
                lab, meta = t.render(f,ff,x,jpg)
            info[f'{page}:{slot}'] = meta
            unsupported = set(meta.get('unsupported_patches',[]))
            for i,p in enumerate(frame['patches']):
                out.append({'page':page,'patch_id':p['patch_id'],'sample_key':p['sample_key'],
                    'slot':slot,'target_lab':lab[i].tolist(), 'supported': i not in unsupported,
                    'target_source_frame':stem, 'panasonic_inverse_residual':float(inverse_residual[i]) if slot in cubes else None})
    rt.dump('targets.json', {'schema':'ricoh-module-targets/1','whitepoint':'D65',
        'source':'independent frozen 50mm 04 scene targets for all six pages; Mount images never define targets',
        'samples':out,'definitions':info,
        'limits':'50mm scene-coordinate transfer is an assumption; GR and BW references are surrogates; Panasonic inverse is nonunique and residuals retained'})


def main():
    inject()
    m = rt.model()
    frozen_targets(m)
    rows = [json.loads(l) for l in s.source(rt.EXCHANGE/'patches.jsonl').read_text().splitlines()]
    raw = np.array([r['raw_rgb'] for r in rows])
    jpg = np.array([r['jpeg_rgb'] for r in rows])
    frames = rt.read('frames.json')['frames']
    wb = np.array([frames[r['frame']]['white_balance']['gains'] for r in rows])
    latent, bad = m.inverse04(jpg,raw*wb)
    np.savez_compressed(rt.LOCAL/'original_inverse.npz',latent=latent,bad=bad)
    (rt.LOCAL/'original_patches.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    print('targets frozen; inverse rejected',int(bad.sum()),flush=True)
    s.finish(rt.LOCAL/'prepare.inputs.json')


if __name__ == '__main__':
    main()
