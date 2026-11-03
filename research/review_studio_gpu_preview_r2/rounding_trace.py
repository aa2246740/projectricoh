"""Locate where the observed 3-4-code differences grow in the uint8 chain."""
import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from color_reference import ReadOnlyLibrary,reference,TEMP,REPORT
from gxr_studio.render.service import RenderService
from gxr_studio.finish.pixels import apply_extra
from gxr_studio.render.params import parse_adjust

mode=sys.argv[1]
cases=json.loads((TEMP/('trace-cases-'+mode+'.json')).read_text())
lib=ReadOnlyLibrary(TEMP/'studio/library');svc=RenderService(TEMP/'studio/app-home',lib)
cpu=[];gpu=[]
for c in cases:
    ref,*_=reference(c,lib,svc);cpu.append(ref)
    p=next((TEMP/('readbacks-trace-'+mode)).glob(c['id']+'__*.rgba'));w,h=map(int,p.stem.split('__')[1].split('x'))
    gpu.append(np.fromfile(p,np.uint8).reshape(h,w,4)[...,:3])
diff=np.abs(gpu[-1].astype(np.int16)-cpu[-1].astype(np.int16)).max(axis=2)
points=np.argwhere(diff>2)
propagated=apply_extra(np.ascontiguousarray(gpu[0]),parse_adjust(cases[-1]['adjust']))
rows=[]
for y,x in points:
    stages=[{'stage':i,'python':c[y,x].tolist(),'gpu':g[y,x].tolist(),'max_code':int(np.abs(c[y,x].astype(int)-g[y,x].astype(int)).max())} for i,(c,g) in enumerate(zip(cpu,gpu))]
    rows.append({'x':int(x),'y':int(y),'stages':stages,'cpu_extra_on_gpu_chain':propagated[y,x].tolist(),'explains_final_exactly':bool(np.array_equal(propagated[y,x],gpu[-1][y,x]))})
result={'stage_order':['recipe_and_curve','black_point_20','plus_saturation_30','plus_vibrance_25','plus_vignette_minus40'],'over_2_pixels':int(len(points)),'points':rows}
(REPORT/('rounding-trace-'+mode+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
