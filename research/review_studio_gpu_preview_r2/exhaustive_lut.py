"""Check every 8-bit RGB input against the production function, without sampling."""
import gc
import hashlib
import json
import resource
import time
from pathlib import Path

import numpy as np
from gxr_studio.gpu.tables import lut_bytes
from gxr_studio.lut.cube import Cube
from gxr_studio.lut.photo import _apply
from gxr_studio.lut.spaces import Target

HERE=Path(__file__).resolve().parent
v=np.linspace(0,1,17)
nodes=np.clip(np.array([[r,g,b] for b in v for g in v for r in v])*[.86,.97,1.05],0,1)
text='TITLE "review exhaustive synthetic"\nLUT_3D_SIZE 17\n'+'\n'.join(' '.join(f'{c:.17g}' for c in row) for row in nodes)+'\n'
cube=Cube.parse(text)
rows=[]
shaped=Cube(table1=np.linspace(0,1,17)[:,None]**np.array([1.1,.9,1.05]),table3=cube.table3,domain_min=cube.domain_min,domain_max=cube.domain_max,range3=cube.range3,range1=cube.range1,title=cube.title)
for name,target in [('review_counterexample',Target(cube,'srgb','srgb')),('shaper_legal_gamut_vlog',Target(shaped,'rec709','vlog','rec2020','vgamut','legal','legal'))]:
    started=time.monotonic()
    data,meta,reason=lut_bytes(target)
    assert reason is None and meta['n']==256 and meta['table8'] and len(data)==256**3*4
    generated=time.monotonic()-started
    table=np.frombuffer(data,np.uint8).reshape(256,256,256,4)
    errors=0;alpha_errors=0;max_diff=0;first=[]
    # A different partition from the implementation's 32-B blocks.
    plane=np.empty((256,256,3),np.uint8)
    plane[...,0]=np.arange(256,dtype=np.uint8)[None,:]
    plane[...,1]=np.arange(256,dtype=np.uint8)[:,None]
    for b in range(256):
        plane[...,2]=b
        expected=_apply(target,plane)
        diff=np.abs(table[b,...,:3].astype(np.int16)-expected.astype(np.int16)).max(axis=2)
        errors+=int((diff!=0).sum());alpha_errors+=int((table[b,...,3]!=255).sum());max_diff=max(max_diff,int(diff.max()))
        if errors and not first:
            for g,r in np.argwhere(diff!=0)[:8]:first.append({'rgb':[int(r),int(g),b],'table':table[b,g,r,:3].tolist(),'production':expected[g,r].tolist()})
    rows.append({'id':name,'inputs':256**3,'channel_values':256**3*3,'mismatching_pixels':errors,'alpha_mismatches':alpha_errors,'max_code':max_diff,'table_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'generation_seconds':generated,'total_seconds':time.monotonic()-started,'peak_rss_bytes_darwin':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'first_mismatches':first})
    del table,data;gc.collect()
(HERE/'exhaustive-lut.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))
assert all(r['mismatching_pixels']==0 and r['alpha_mismatches']==0 for r in rows)
