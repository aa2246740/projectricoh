"""Fit the ten local LUTs, retaining and encoding the actual integer solution."""
from pathlib import Path
import os
import sys
import shutil
import json
import time
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
for key in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
os.environ['TMPDIR']='/Volumes/Workspace/Scratch/tmp/projectricoh/g152'
sys.path.insert(0,str(HERE))
from dat_format import expand,refresh_entry,sha
sys.path.insert(0,str(ROOT/'research/film_engines_eval'))
import guard
guard.LOCAL=HERE/'local'
guard.SCRATCH=Path(os.environ['TMPDIR'])
import numpy as np
from camera import Camera
from convert import prepare,DEFAULT_SCENES
from cube import Cube
from spaces import Target
from engines_ceiling import scene_target
from ceiling import build_sets
from fit import Problem,score

JOBS=(
 ('M9 STD','Leica_M9_STD_33_Rec709.cube',False),
 ('HNCS HiCon','Hasselblad_HNCS_HiContrast_33_Rec709.cube',False),
 ('Tri-X 400','fotufilm_trix400_srgb.cube',True),
 ('Portra 400','fotufilm_portra400_srgb.cube',True),
 ('Velvia 50','fotufilm_velvia50_srgb.cube',True),
 ('Kodachrome25','fotufilm_kodachrome25_srgb.cube',True),
 ('HNCS LowSat','Hasselblad_HNCS_LowSat_33_Rec709.cube',False),
 ('Vision3 500T','fotufilm_vision500t_srgb.cube',True),
 ('instax mini','fotufilm_instaxmini_srgb.cube',True),
 ('Metropolis','fotufilm_lomochromemetropolis_srgb.cube',True),
)

def local_inputs():
    directory=HERE/'local/luts';directory.mkdir(parents=True,exist_ok=True)
    receipt=[]
    for _,name,film in JOBS:
        source=ROOT/'research/fotufilm_bake/local/cubes'/name if film else Path('/Users/wu/Downloads/waiting ')/name
        target=directory/name
        if not target.exists():shutil.copyfile(source,target)
        assert target.read_bytes()==source.read_bytes()
        receipt.append(dict(source=str(source),copy=str(target.relative_to(ROOT)),sha256=sha(target.read_bytes())))
    for name in ('LICENSE-CC-BY-SA-4.0.txt','FILM-PROFILES-NOTICE.txt','FOTUFILM-NOTICE.txt'):
        shutil.copyfile(ROOT/'research/fotufilm_bake/local/cubes'/name,directory/name)
    # Reuse immutable scene samples; new calculations use our own cache directory.
    src=ROOT/'research/film_engines_eval/local/scene_cache';dst=HERE/'local/scene_cache'
    shutil.copytree(src,dst,dirs_exist_ok=True)
    (HERE/'lut_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

def render_encoded(camera,entry,x):
    """Decode final curve, matrix and sector bytes. No slot-based grey branch."""
    curve=camera.mm.Curve.from_rows(*camera.src.unpack_tone(entry[20:82],entry[82:115]),name='g152')
    row=camera.mm.MatrixRow.from_bytes(entry[216:244])
    y,ci=row.apply(curve(np.asarray(x)))
    if entry[115:211]==bytes(96):
        ab=np.zeros((24,2),dtype=int)
        # The encoded table's absolute coefficients are zero in every sector.
        # Interpolation of these coefficients is zero for every input hue.
        coefficients=(ab[:,0]-1j*ab[:,1])/32
        co=ci*(np.sum(coefficients)/len(coefficients))
    else:
        ab=np.array([camera.fs.decode_word(entry[115+4*i:119+4*i]) for i in range(24)])
        z=camera.fs.Z_of_words(ab[:,0],ab[:,1],camera.E.ctx)
        co=camera.E.table.forward(ci,z)[0]
    return np.clip(camera.mm.rgb_from_ycc(y,co),0,255)

def encoded(base,q,bw,stock):
    out=bytearray(base)
    out[20:82]=stock[20:82]
    # Safe mode has a common RGB curve. Keep the original physical node row.
    out[82:115]=bytes(q['q'][1].tolist())
    out[216:272]=q['row'].to_bytes()+q['row2'].to_bytes()
    if not bw:out[115:211]=q['colour']
    else:
        assert out[115:211]==bytes(96)
        out[284:346]=out[20:82];out[346:379]=out[82:115]
    out[456:518]=out[20:82];out[518:551]=out[82:115]
    return refresh_entry(out)

def fit_one(camera,scenes,cube,interpretation,bw,base,stock):
    target=scene_target(cube) if interpretation=='scene' else Target(cube,'srgb','srgb')
    s=build_sets(camera,target,scenes);ref=scenes[0]
    problem=Problem(camera,s['x'],s['desired'],variant='safe',bw=bw,sample_weights=s['sw'])
    rampx=np.repeat(camera.curve.xs[:,None],3,axis=1)
    ramp=target.render(camera.stock(rampx),camera.xyz(rampx,ref['neutral'],ref['matrix']))
    start=problem.theta0.copy();start[problem.qstart:problem.t2start]=np.maximum.accumulate(ramp@np.array([.299,.587,.114]))-camera.curve.ys
    result,solver=problem.solve(start,100)
    q=problem.quantize(result.x)
    entry=encoded(base,q,bw,stock)
    # Both predictions and CRCs come from the exact stored integer rows.
    synthetic,_=score(camera,camera.stock(s['testx']),np.rint(render_encoded(camera,entry,s['testx'])),s['testt'])
    scene,_=score(camera,camera.stock(s['hx']),np.rint(render_encoded(camera,entry,s['hx'])),s['ht'])
    if bw:
        samples=np.vstack([s['testx'],s['hx']]);pixels=render_encoded(camera,entry,samples)
        assert np.max(np.ptp(pixels,axis=1))==0
    doc=dict(interpretation=interpretation,solver=solver,synthetic_holdout=synthetic,scene_holdout=scene,
             integer_curves=q['q'].tolist(),matrix_hex=entry[216:272].hex(),colour_hex=entry[115:211].hex(),
             theta=q['theta'].tolist(),entry_hex=entry.hex(),entry_sha256=sha(entry),
             bw_from_encoded_rows=bw,sector_safety=guard.jsonable(q['safety']))
    return entry,doc

def main():
    local_inputs();camera=Camera();scenes=prepare(camera,DEFAULT_SCENES,280)
    raw=(ROOT/'firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT').read_bytes()
    effects=[];evidence=[]
    for index,(name,filename,film) in enumerate(JOBS):
        t=time.monotonic();bw=index==2;base=3 if bw else 5
        cube=Cube.read(HERE/'local/luts'/filename)
        options=[]
        for interpretation in ('after04','scene') if film else ('after04',):
            print('fit',index+1,name,interpretation,flush=True)
            entry,doc=fit_one(camera,scenes,cube,interpretation,bw,expand(raw,0,base),expand(raw,0,4))
            options.append((entry,doc))
            directory=HERE/'local/fits'/f'{index+1:02d}-{interpretation}';directory.mkdir(parents=True,exist_ok=True)
            guard.dump(directory/'quantized.json',doc)
        entry,chosen=min(options,key=lambda pair:pair[1]['scene_holdout']['de00']['median'])
        row=dict(name=name,base=base,mask=7,entry_hex=entry.hex(),source_sha256=cube.source_sha256,
                 source=filename,interpretation=chosen['interpretation'],license='CC BY-SA 4.0' if film else 'local data',
                 attribution='Fotufilm https://fotufilm.com; Copyright 2026 MUAStudio Inc.; GXR project adaptation' if film else '')
        effects.append(row)
        evidence.append(dict(index=index+1,name=name,base=base,seconds=time.monotonic()-t,
                             selected=chosen['interpretation'],options=[{k:v for k,v in d.items() if k not in ('entry_hex','theta','integer_curves','matrix_hex','colour_hex')} for _,d in options]))
        guard.dump(HERE/'local/effects.json',effects)
        (HERE/'fit_results.json').write_text(json.dumps(guard.jsonable(evidence),indent=2)+'\n')
        print('selected',name,chosen['interpretation'],round(chosen['synthetic_holdout']['similarity']*100,2),
              round(chosen['scene_holdout']['similarity']*100,2),'seconds',round(time.monotonic()-t,2),flush=True)
    (HERE/'fit_provenance.json').write_text(json.dumps(guard.jsonable(camera.description()),indent=2)+'\n')

if __name__=='__main__':main()
