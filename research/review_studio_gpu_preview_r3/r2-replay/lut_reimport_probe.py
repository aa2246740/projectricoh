import sys
sys.path.insert(0, '/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3/source/src')
"""Exercise delete and re-import through the shipped APIs, using a synthetic LUT."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

import numpy as np
from fastapi.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
from gxr_studio.lut.photo import _apply

HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3/r2-replay/lut-reimport')
audit.forbid_volumes()
for p in ('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3/unused-protected-0','/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3/unused-protected-1','/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3/unused-protected-2'):
    audit.protect(p);audit.forbid_reads(p)
s=Settings(library_dir=TEMP/'library',home_dir=TEMP/'home',export_dir=TEMP/'export',volumes_roots=(TEMP/'volumes',),port=49763,token='r2-lut-synthetic-only',min_free_bytes=0)
v=np.linspace(0,1,17)
nodes=np.clip(np.array([[r,g,b] for b in v for g in v for r in v])*[.86,.97,1.05],0,1)
cube=('TITLE "r2 synthetic"\nLUT_3D_SIZE 17\n'+'\n'.join(' '.join(f'{c:.17g}' for c in row) for row in nodes)+'\n').encode()
samples=np.array([[[64,128,192],[123,45,67],[219,181,3],[0,255,17]]],np.uint8)
rows=[]
with TestClient(create_app(s),base_url='http://127.0.0.1:49763',headers={'X-GXR-Token':s.token}) as client:
    old=None
    for label,space in [('first','srgb'),('reimported','rec709')]:
        upload=client.post('/api/lut/upload',content=cube,headers={'X-GXR-Filename':'r2-synthetic.cube'})
        assert upload.status_code==200,upload.text
        cid=upload.json()['cube_id']
        item=client.patch(f'/api/luts/{cid}',json={'input_space':space,'output_space':'srgb'})
        assert item.status_code==200,item.text
        response=client.get(f'/api/luts/{cid}/table')
        assert response.status_code==200,response.text
        meta=json.loads(unquote(response.headers['x-gxr-lut']))
        target,_=client.app.state.ctx.render.luts.target(cid,persist=False)
        expected=_apply(target,samples)
        table=np.frombuffer(response.content,np.uint8).reshape(256,256,256,4)
        actual=table[samples[...,2],samples[...,1],samples[...,0],:3]
        row={'case':label,'input_space':space,'version':item.json()['version'],'key':meta['key'],'etag':response.headers['etag'],'bytes':len(response.content),'sha256':hashlib.sha256(response.content).hexdigest(),'samples':samples.tolist(),'production':expected.tolist(),'gpu_table':actual.tolist(),'samples_equal':bool(np.array_equal(actual,expected))}
        rows.append(row)
        if label=='first':
            old=row
            deleted=client.delete(f'/api/luts/{cid}')
            assert deleted.status_code==200,deleted.text
    result={'rows':rows,'same_key_after_delete_reimport':rows[0]['key']==rows[1]['key'],'same_table_after_space_change':rows[0]['sha256']==rows[1]['sha256'],'wrong_current_table':not rows[1]['samples_equal']}
(HERE/'lut-reimport-probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
