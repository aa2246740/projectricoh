"""Compare saved engine pixels against production Python before JPEG compression.

Pixel counts and Delta E values are kept unrounded. The geometry exception is a
one-pixel band around the Python source-coverage boundary, not every crop edge.
"""
import json
import math
from pathlib import Path
import sqlite3
import sys
import numpy as np
from gxr_studio.engine.colour import delta_e00, lab_from_codes
from gxr_studio.finish.compose import finish_array, load_jpeg
from gxr_studio.finish.spec import factory_frame, factory_stamp, parse_geometry
from gxr_studio.finish.geometry import warp_valid
from gxr_studio.gpu.box import final_box
from gxr_studio.lut.photo import _apply
from gxr_studio.lut.scene import scene_colour
from gxr_studio.lut.spaces import DISPLAY
from gxr_studio.raw import NEUTRAL, half_res_codes, open_dng, orient_array
from gxr_studio.render import chain
from gxr_studio.render.params import EditState, parse_adjust, parse_curve, parse_recipe
from gxr_studio.render.service import RenderService
from gxr_studio.render.tones import channel_gains, display_table

REPORT=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')

class ReadOnlyLibrary:
    def __init__(self,root):
        self.root=root
        self.db=sqlite3.connect(f'file:{root}/.studio/index.sqlite?mode=ro',uri=True)
        self.db.row_factory=sqlite3.Row
    def abspath(self,rel): return self.root/rel
    def shot(self,sid):
        d=dict(self.db.execute('SELECT * FROM shots WHERE shot_id=?',(sid,)).fetchone())
        d['files']={r['kind']:dict(r) for r in self.db.execute('SELECT * FROM files WHERE shot_id=?',(sid,))}
        return d

def reference(c,lib,svc):
    shot=lib.shot(c['photo'])
    adjust=parse_adjust(c.get('adjust') or {})
    master=parse_curve({'master':c['curve']}) if c.get('curve') else None
    geom=parse_geometry(c.get('geometry') or {})
    sel=parse_recipe(c['recipe']) if c.get('recipe') else None
    edit=EditState(recipe=sel,adjust=adjust,master=master,geometry=geom)
    raw=False
    needs_raw=bool(sel or 'jpg' not in shot['files'])
    target=None
    if c.get('lut'):
        target,_=svc.luts.target(c['lut'])
        needs_raw=needs_raw or target.input_space not in DISPLAY
    dng=None
    if needs_raw:
        dng=open_dng(lib.abspath(shot['files']['dng']['relpath']))
        codes=np.ascontiguousarray(orient_array(half_res_codes(dng),dng.orientation),np.float32)
    try:
        if target is not None:
            if target.input_space not in DISPLAY:
                rgb=_apply(target,NEUTRAL.display(codes),scene_colour(dng).xyz(codes))
            else:
                base=chain.chroma_u8(codes,svc.preview_bake(svc.plan(shot,EditState(recipe=sel))),None,None) if needs_raw else load_jpeg(lib.abspath(shot['files']['jpg']['relpath']),None)
                rgb=_apply(target,base)
        elif needs_raw:
            rgb=chain.chroma_u8(codes,svc.preview_bake(svc.plan(shot,edit)),channel_gains(adjust),display_table(adjust,master));raw=True
        else: rgb=load_jpeg(lib.abspath(shot['files']['jpg']['relpath']),None)
    finally:
        if dng is not None:dng.release()
    height,width=rgb.shape[:2]
    crop=c.get('crop');rect=tuple(crop['rect']) if crop else None
    out,_=finish_array(rgb,edit,stage=c['stage'],frame=factory_frame(),stamp=factory_stamp(),crop_rect=rect,meta={},taken=None,file_time=None,from_raw=raw,crop_preset=crop.get('preset') if crop else None)
    valid=warp_valid(width,height,geom)
    padded=np.pad(valid,1,constant_values=False)
    eroded=np.ones_like(valid);dilated=np.zeros_like(valid)
    for y in range(3):
        for x in range(3):
            eroded&=padded[y:y+valid.shape[0],x:x+valid.shape[1]]
            dilated|=padded[y:y+valid.shape[0],x:x+valid.shape[1]]
    band=dilated&~eroded
    box=(0,0,valid.shape[1],valid.shape[0])
    if c['stage']=='final':
        box,_=final_box(width,height,geom,rect,crop.get('preset') if crop else None)
        x,y,w,h=box;band=band[y:y+h,x:x+w];valid=valid[y:y+h,x:x+w]
    return np.ascontiguousarray(out),band,valid,(width,height),box

def stats(gpu,ref,band,valid):
    assert gpu.shape==ref.shape,(gpu.shape,ref.shape)
    diff=np.abs(gpu.astype(np.int16)-ref.astype(np.int16)).max(axis=2)
    a=gpu.reshape(-1,3);b=ref.reshape(-1,3)
    total=0.;de_max=0.;de_parts=[]
    for at in range(0,len(a),1<<18):
        de=delta_e00(lab_from_codes(a[at:at+(1<<18)]),lab_from_codes(b[at:at+(1<<18)]))
        total+=float(de.sum());de_max=max(de_max,float(de.max()));de_parts.append(de)
    de=np.concatenate(de_parts)
    coords=[]
    for y,x in np.argwhere(diff>1)[:24]:
        coords.append({'x':int(x),'y':int(y),'gpu':gpu[y,x].tolist(),'python':ref[y,x].tolist(),'max_code':int(diff[y,x]),'edge_band':bool(band[y,x]),'valid':bool(valid[y,x])})
    return {'pixels':int(diff.size),'identical_pixels':int((diff==0).sum()),'within_1_pixels':int((diff<=1).sum()),'within_1':float((diff<=1).mean()),'over_1_pixels':int((diff>1).sum()),'over_2_pixels':int((diff>2).sum()),'mean_delta_e00':total/diff.size,'p95_delta_e00':float(np.percentile(de,95)),'max_delta_e00':de_max,'max_code':int(diff.max()),'edge_band_pixels':int(band.sum()),'over_2_outside_edge_band':int(((diff>2)&~band).sum()),'max_code_outside_edge_band':int(diff[~band].max()) if (~band).any() else 0,'example_differences':coords}

def main():
    lib=ReadOnlyLibrary(TEMP/'studio/library');svc=RenderService(TEMP/'studio/app-home',lib)
    cases=json.loads((TEMP/'real-cases.json').read_text());rows=[]
    for c in cases:
        files=list((TEMP/('readbacks-'+sys.argv[1])).glob(c['id']+'__*.rgba'))
        if not files:rows.append({'id':c['id'],'error':'missing readback'});continue
        w,h=map(int,files[0].stem.split('__')[1].split('x'))
        gpu=np.fromfile(files[0],np.uint8).reshape(h,w,4)[...,:3]
        ref,band,valid,size,box=reference(c,lib,svc)
        row={'id':c['id'],'w':w,'h':h,'source_layer':size,'box':box,**stats(gpu,ref,band,valid)}
        rows.append(row);print(json.dumps(row),flush=True)
    (REPORT/('independent-parity-'+sys.argv[1]+'.json')).write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
