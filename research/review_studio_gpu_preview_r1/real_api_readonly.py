import json
from pathlib import Path
from fastapi.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings

TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1')
REPORT=Path(__file__).resolve().parent
root=TEMP/'baseline'
s=Settings(library_dir=root/'library',home_dir=root/'app-home',export_dir=root/'export',volumes_roots=(root/'empty-volumes',),port=49742,token='baseline-review-only',min_free_bytes=0)
audit.forbid_volumes()
for p in ('/Users/wu/Pictures/GXR Studio','/Users/wu/Pictures/GXR 导出','/Users/wu/Library/Application Support/GXR Studio'):
    audit.protect(p);audit.forbid_reads(p)
case=json.loads((TEMP/'real-cases.json').read_text())[0]
cid=json.loads((REPORT/'real-inputs.json').read_text())['luts']['display']
urls=[('GET',f'/api/photos/{case["photo"]}/{suffix}',None) for suffix in ['gpu','raw','camera-jpg','bake']]
urls += [('GET',f'/api/luts/{cid}/table',None),('POST',f'/api/photos/{case["photo"]}/gpu/box',{'width':2144,'height':1424})]
rows=[]
with TestClient(create_app(s),base_url='http://127.0.0.1:49742',headers={'X-GXR-Token':s.token}) as client:
    with audit.AuditRecorder(watch=(str(root),)) as record:
        for method,url,body in urls:
            r=client.request(method,url,json=body)
            rows.append({'url':url,'status':r.status_code,'bytes':len(r.content)})
    result={'responses':rows,'writes':[{'op':x.op,'path':x.path} for x in record.writes]}
(REPORT/'real-api-readonly.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
