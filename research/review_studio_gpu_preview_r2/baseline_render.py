"""Run the same real-input API requests on HEAD or an origin/main source snapshot."""
import hashlib
import json
from pathlib import Path
import sys
import io

TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
REPORT=Path(__file__).resolve().parent
mode=sys.argv[1]
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview') if mode=='head' else TEMP/'main-snapshot'
sys.path.insert(0,str(WT/'src'))
from PIL import Image
from fastapi.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings

audit.forbid_volumes()
for p in ('/Users/wu/Pictures/GXR Studio','/Users/wu/Pictures/GXR 导出','/Users/wu/Library/Application Support/GXR Studio'):
    audit.protect(p);audit.forbid_reads(p)
root=TEMP/('baseline-'+mode)
s=Settings(library_dir=root/'library',home_dir=root/'app-home',export_dir=root/'export',volumes_roots=(root/'empty-volumes',),port=49762,token='baseline-review-only',min_free_bytes=0)
rows=[]
with TestClient(create_app(s),base_url='http://127.0.0.1:49762',headers={'X-GXR-Token':s.token}) as client:
    cases=json.loads((TEMP/'real-cases.json').read_text())
    if mode=='head':
        from unittest.mock import patch
        from gxr_studio.api import gpu_routes
        with patch.object(gpu_routes,'_raw_source',wraps=gpu_routes._raw_source) as raw,patch.object(client.app.state.ctx.render,'warm_preview_bakes') as warm:
            disabled=client.get(f'/api/photos/{cases[0]["photo"]}/gpu')
            probe={'status':disabled.status_code,'response':disabled.json(),'raw_layout_calls':raw.call_count,'warm_preview_calls':warm.call_count}
            (REPORT/'flag-off-api-probe.json').write_text(json.dumps(probe,indent=2)+'\n')
            assert probe=={'status':200,'response':{'enabled':False},'raw_layout_calls':0,'warm_preview_calls':0}
    if len(sys.argv)>2:cases=[c for c in cases if c['id']==sys.argv[2]]
    for c in cases:
        body={'recipe':c.get('recipe'),'lut':c.get('lut'),'adjust':c.get('adjust') or {},'curve':{'master':c['curve']} if c.get('curve') else None,'geometry':c.get('geometry') or {},'crop':c.get('crop'),'frame':{'style':'none'},'stamp':{'enabled':False}}
        r=client.post(f'/api/photos/{c["photo"]}/render?stage={c["stage"]}&size=full',json=body)
        row={'id':c['id'],'status':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'headers':{k:v for k,v in r.headers.items() if k.lower().startswith('x-gxr-') and 'cache' not in k.lower()}}
        if r.status_code==200:
            im=Image.open(io.BytesIO(r.content));row['size']=im.size;row['pixel_sha256']=hashlib.sha256(im.tobytes()).hexdigest()
            dest=TEMP/('baseline-responses-'+mode);dest.mkdir(exist_ok=True)
            (dest/(c['id']+'.jpg')).write_bytes(r.content)
            if len(sys.argv)>2:
                dest=TEMP/'jpeg-forensic';dest.mkdir(exist_ok=True)
                (dest/(mode+'.jpg')).write_bytes(r.content)
        else:row['error']=r.text
        rows.append(row);print(json.dumps(row),flush=True)
suffix='-forensic' if len(sys.argv)>2 else ''
(REPORT/f'baseline-api-{mode}{suffix}.json').write_text(json.dumps({'source':str(WT),'rows':rows},indent=2)+'\n')
