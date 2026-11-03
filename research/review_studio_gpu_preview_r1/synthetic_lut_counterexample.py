"""A rerunnable public-data-only challenge to the advertised parity thresholds."""
import io,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
REPORT=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1')
sys.path.insert(0,str(WT/'tests'))
from gpu_support import run_engine
from test_gpu_parity import _bake,_dngs,_stats,_finish
from gxr_studio.finish.compose import load_jpeg
from gxr_studio.gpu.source import raw_layout
from gxr_studio.gpu.tables import bake_bytes,lut_bytes
from gxr_studio.lut.cube import Cube
from gxr_studio.lut.spaces import Target
from gxr_studio.lut.photo import _apply
from gxr_studio.raw import open_dng,half_res_codes,orient_array
from gxr_studio.render.chain import chroma_u8
from gxr_studio.render.params import EditState,parse_adjust

v=np.linspace(0,1,17)
values=np.array([[r,g,b] for b in v for g in v for r in v])
cube=Cube.parse('TITLE "synthetic quantization challenge"\nLUT_3D_SIZE 17\n'+'\n'.join(' '.join(f'{c:.17g}' for c in row) for row in np.clip(values*[.86,.97,1.05],0,1))+'\n')
target=Target(cube,'srgb','srgb');ld,lm,reason=lut_bytes(target);assert reason is None
bk=_bake();bd,bm=bake_bytes(bk)
raw_bytes=_dngs()['a'];dng=open_dng(raw_bytes);layout,reason=raw_layout(dng);assert reason is None
codes=np.ascontiguousarray(orient_array(half_res_codes(dng),dng.orientation),np.float32)
yy,xx=np.mgrid[0:256,0:256]
rgb=np.stack([xx,yy,(xx+yy)//2],axis=-1).astype(np.uint8)
buf=io.BytesIO();Image.fromarray(rgb).save(buf,'JPEG',quality=100,subsampling=0)
jpg=buf.getvalue();path=TEMP/'synthetic-lut.jpg';path.write_bytes(jpg);decoded=load_jpeg(path,None)
adjust={'exposure_ev':.3,'contrast':20,'saturation':-20}
edit=EditState(adjust=parse_adjust(adjust));geometry={'straighten':0,'rotate90':0,'flip':False,'box':None}
files={'/raw.dng':raw_bytes,'/camera.jpg':jpg,'/lut.bin':ld,'/bake.bin':bd}
cases=[{'id':'raw_lut_rounding','source':'raw','raw':{'url':'/raw.dng','layout':layout},'bake':{'url':'/bake.bin','key':'synthetic','meta':bm},'lut':{'url':'/lut.bin','key':'synthetic','meta':lm},'look':{'recipe':'synthetic','lut':'synthetic','lutStrength':1,'adjust':adjust,'curve':None},'geometry':geometry},
       {'id':'jpg_lut_rounding','source':'jpg','jpg':'/camera.jpg','lut':{'url':'/lut.bin','key':'synthetic','meta':lm},'look':{'recipe':None,'lut':'synthetic','lutStrength':1,'adjust':{'highlight':-30},'curve':None},'geometry':geometry}]
out,summary=run_engine(TEMP/'synthetic-parity',files,cases)
refs={'raw_lut_rounding':_finish(_apply(target,chroma_u8(codes,bk,None,None)),edit,from_raw=False),
      'jpg_lut_rounding':_finish(_apply(target,decoded),EditState(adjust=parse_adjust({'highlight':-30})),from_raw=False)}
rows=[{'id':cid,**_stats(out[cid],ref)} for cid,ref in refs.items()]
for row in rows:row['advertised_gate_pass']=row['within_1']>=.9999 and row['mean']<=.01
result={'adapter':summary,'all_inputs_synthetic':True,'lut_node_formula':'clip([r,g,b] * [0.86,0.97,1.05],0,1), 17 cubed','rows':rows}
(REPORT/'synthetic-lut-counterexample.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(0 if all(x['advertised_gate_pass'] for x in rows) else 1)
