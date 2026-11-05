"""Deterministic scene sampling and colour metrics using the current Studio path."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from support import ROOT, HERE, DATA, SCRATCH, digest, exif, dump, check_time
from gxr_studio.raw.dng import Dng
from gxr_studio.lut.scene import scene_colour
from gxr_studio.lut.cube import Cube
from gxr_studio.lut.spaces import encode, decode, matrix, xyz_to_encoded, to_srgb, Target
from gxr_studio.engine.colour import lab_from_codes, delta_e00

CREATORS = ROOT / 'artifacts/downloads/panasonic-25th-luts-20261102'

def stats(v):
    v = np.asarray(v, float).ravel()
    if not len(v):
        return {'n':0, 'median':None, 'p95':None, 'max':None}
    if not np.isfinite(v).all():
        raise ValueError('Non-finite metric')
    return {'n':len(v), 'median':float(np.median(v)), 'p95':float(np.percentile(v,95)),
            'max':float(v.max()), 'mean':float(v.mean())}

def de(a,b):
    return delta_e00(lab_from_codes(np.asarray(a)*255),lab_from_codes(np.asarray(b)*255))

def rgb_out(codes, space='gamma24'):
    return np.clip(to_srgb(codes,space),0,1)

def selected_paths():
    paths = [
        'captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051131.DNG',
        'captures/a12-50/2026-10-19/stage2c-first-run/R8051144.DNG',
        'captures/a12-50/2026-10-19/stage2c-first-run/R8051145.DNG',
        'captures/a12-50/2026-10-19/stage2c-first-run/R8051147.DNG',
        *['captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228/R80512'+str(n)+'.DNG'
          for n in (19,20,22,24,26,28)],
        *['captures/street-g137-20261031/dng/R805'+str(n)+'.DNG' for n in (1530,1533,1536,1562,1680)],
        *['captures/mount-g150-20261101/R805'+str(n)+'.DNG' for n in (1691,1695,1701)],
        *['captures/looks-g152-20261102/R805'+str(n)+'.DNG' for n in (1839,1842)],
    ]
    for p in paths:
        if not (ROOT/p).is_file():
            raise FileNotFoundError(p)
    return paths

def scene(path, width=96):
    """A recorded sparse grid of 2x2 Bayer means, identical code-domain arithmetic."""
    path = ROOT/path if not Path(path).is_absolute() else Path(path)
    hsh = digest(path)
    cache = SCRATCH / (hsh[:20] + '-w' + str(width) + '.npz')
    meta = exif(path)
    if cache.exists():
        with np.load(cache,allow_pickle=False) as z:
            return {k:z[k].copy() for k in z.files}, meta
    d = Dng(path)
    col = scene_colour(d)
    y0,x0,h,w = d.crop_window()
    height = max(2,round(h*width/w))
    ys = y0 + 2*np.linspace(0,(h-2)//2,height).astype(int)
    xs = x0 + 2*np.linspace(0,(w-2)//2,width).astype(int)
    yy,xx = np.meshgrid(ys,xs,indexing='ij')
    raw = np.zeros((height,width,3))
    counts = np.zeros((height,width,3))
    clipped = np.zeros((height,width),bool)
    for dy in (0,1):
        for dx in (0,1):
            color = d.cfa_at(yy+dy,xx+dx)
            value = d.normalised_at(yy+dy,xx+dx)
            clipped |= value >= .98
            for ch in range(3):
                mask = color == ch
                raw[...,ch] += value*mask
                counts[...,ch] += mask
    raw /= counts
    codes = raw/d.as_shot_neutral*4095
    xyz = col.xyz(codes.reshape(-1,3)).reshape(codes.shape)
    valid = (~clipped) & np.isfinite(xyz).all(axis=-1)
    arrays = {'codes':codes.reshape(-1,3), 'xyz':xyz.reshape(-1,3), 'raw':raw.reshape(-1,3),
              'valid':valid.ravel(), 'shape':np.array([height,width]),
              'neutral':col.neutral, 'matrix':col.matrix}
    np.savez_compressed(cache,**arrays)
    d.release()
    return arrays,meta

def scenes():
    out=[]
    for path in selected_paths():
        check_time()
        arrays,meta = scene(path)
        record = {'path':path,'sha256':digest(ROOT/path),**meta,
                  'samples_total':len(arrays['xyz']), 'samples_valid':int(arrays['valid'].sum()),
                  'raw_clipped_share':float((~arrays['valid']).mean()),
                  'matrix':arrays['matrix'].tolist(), 'neutral':arrays['neutral'].tolist()}
        out.append((arrays,record))
    return out

def synthetic():
    values=np.linspace(0,1,17)
    normal=np.array(np.meshgrid(values,values,values,indexing='ij')).reshape(3,-1).T
    rng=np.random.default_rng(20261102)
    hdr=np.exp(rng.uniform(np.log(.001),np.log(16),(8192,1)))*rng.uniform(.05,1.5,(8192,3))
    gray=np.repeat(np.geomspace(.0001,16,513)[:,None],3,axis=1)
    return {'grid_0_1':normal@matrix('rec709').T, 'hdr':hdr@matrix('rec709').T,
            'gray':gray@matrix('rec709').T}

def creator_jobs():
    out=[]
    for p in sorted(CREATORS.rglob('*.cube')):
        family=p.parent.name
        name=('Agfa LeBox' if family=='agfa-lebox' else 'Y2K Plady' if family=='unnamed-8b73'
              else '千禧回声 '+('A' if p.name.startswith('73ec') else 'B'))
        out.append({'name':name,'path':p,'input':'srgb','output':'srgb','family':'creator',
                    'space_status':'sRGB 明示' if family=='agfa-lebox' else 'sRGB 显示参考，推断'})
    if len(out)!=4:
        raise ValueError('Expected four creator LUTs')
    return out

def alchemy_jobs():
    choices=[
      ('Phocus Standard','Hasselblad','Hasselblad_Standard_Phocus_X2D_VLog_sRGB_65.cube','srgb'),
      ('Phocus Nature','Hasselblad','Hasselblad_Nature_Phocus_X2D_VLog_sRGB_65.cube','srgb'),
      ('ARRI Classic709','Arri','ARRI_LogC2Video_Classic709_VLog.cube','gamma24'),
      ('Kodak 2383','Cineon','Cineon_to_Kodak_2383_D65_VLog.cube','gamma24'),
      ('Fuji 3513DI','Cineon','Cineon_to_Fuji_3513DI_D65_VLog.cube','gamma24'),
      ('Eterna BB','Fujifilm','FLog2C_to_ETERNA-BB_VLog.cube','gamma24'),
      ('RED Film Bias','Nikon','RED_FilmBias_Rec2020_N-Log_to_Rec709_BT1886_VLog.cube','gamma24'),
      ('Classic Chrome','Fujifilm','FLog2C_to_CLASSIC-CHROME_VLog.cube','gamma24'),
      ('Classic Neg','Fujifilm','FLog2C_to_CLASSIC-Neg_VLog.cube','gamma24'),
      ('Eterna','Fujifilm','FLog2C_to_ETERNA_VLog.cube','gamma24'),
      ('Acros','Fujifilm','FLog2C_to_ACROS_VLog.cube','gamma24'),
      ('Leica Classic','Leica','L-Log_to_Classic_VLog.cube','gamma24'),
      ('RED IPP2','RED','REC709_MEDIUM_CONTRAST_Soft_VLog.cube','gamma24'),
    ]
    return [{'name':name,'path':DATA/'Luts'/family/file,'input':'vlog','output':output,
             'family':'alchemy','space_status':'V-Log / V-Gamut 明示'}
            for name,family,file,output in choices]

def input_receipts(scene_rows):
    paths=[p for base in (DATA,CREATORS,ROOT/'artifacts/downloads/fuji-luts')
           for p in base.rglob('*') if p.is_file()]
    paths += [ROOT/r['path'] for _,r in scene_rows]
    return [{'path':str(p.relative_to(ROOT)),'sha256':digest(p),'bytes':p.stat().st_size}
            for p in sorted(set(paths))]

def camera_model(ui=0, *, geometry=None):
    from gxr_studio.camdata.datcodec import parse
    from gxr_studio.camdata.calib import stock_words_of_entry
    from gxr_studio.engine.model import Model
    dat_path=ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT'
    dat=parse(dat_path.read_bytes())
    npz=ROOT/'research/color_fit_v2/06_classic_neg/round4/local/cache/data_200.npz'
    ring=ROOT/'research/hue_ring/local/ring_model_v2.json'
    sys.path.insert(0, str(ROOT/'research/module_adapt'))
    from c040 import module_spec, geometry_mode
    unit = ('a12-50', 'a12-28', 'mount-a12')[ui]
    with np.load(npz,allow_pickle=False) as z:
        stock=stock_words_of_entry(dat.entry_of(ui,4))
        if ui == 0 and not np.array_equal(stock,z['stock']):
            raise ValueError('Calibration stock differs')
        d0, d1 = z['d0'].copy(), z['d1'].copy()
        if ui != 0:
            official = json.loads((ROOT/'research/module_adapt/local/official_parameters.json').read_text())['units'][('50mm','28mm','mount')[ui]]
            display = json.loads((ROOT/'research/stage2e_verification/local/measurements.json').read_text())['frames']['R8051160']['meta']['display']
            d0, d1 = np.zeros(24), np.zeros(24)
            for i, color in enumerate(('orange','green','blue','red','magenta')):
                selected = np.array([bool(int(official['mask'][i]) & (1 << j)) for j in range(24)])
                level = int(display[color+'_hue'])-1
                d0[selected] = np.asarray(official['d0_levels'])[level, selected]
                d1[selected] = np.asarray(official['d1_levels'])[level, selected]
        model=Model(stock,d0,d1,module_spec(json.loads(ring.read_text()),unit,geometry))
    return model,dat,{'dat':str(dat_path.relative_to(ROOT)),'dat_sha256':digest(dat_path),
                     'npz':str(npz.relative_to(ROOT)),'npz_sha256':digest(npz),
                     'ring':str(ring.relative_to(ROOT)),'ring_sha256':digest(ring),
                     'model_unit':unit,'calibrated_unit':'a12-50','calibrated_iso':200,
                     'c040_geometry':geometry_mode(geometry),
                     'other_units':'module-native C040/C080; empirical kernel transferred from 50mm; legacy evaluator does not apply a per-unit RAW residual'}
