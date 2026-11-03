"""Reject HDR exports to a discovered card, a card link and the library."""
import hashlib
import json
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr/edits')
sys.path.insert(0,str(ROOT/'studio/src'))
from fastapi.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
audit.forbid_network(True)
audit.forbid_volumes()
card=TMP/'volumes/NO NAME'
alias=TMP/'export-card-link'
alias.symlink_to(card/'DCIM',target_is_directory=True)
def snapshot():
    return {str(p.relative_to(card)):hashlib.sha256(p.read_bytes()).hexdigest() for p in card.rglob('*') if p.is_file()}
before=snapshot()
settings=Settings(library_dir=TMP/'library',home_dir=TMP/'app-home',export_dir=TMP/'exports',volumes_roots=(TMP/'volumes',),
                  token='review-local-token',port=8765,min_free_bytes=0,web_dir=ROOT/'studio/web')
results=[]
with TestClient(create_app(settings),base_url='http://127.0.0.1:8765',headers={'X-GXR-Token':settings.token}) as client:
    photo=next(p for p in client.get('/api/photos').json() if p['name']=='ORIENT1')
    for label,dest in [('card',card/'DCIM'),('card_link',alias),('library',settings.library_dir/'.studio/hdr')]:
        with audit.AuditRecorder(watch=(str(card),)) as rec:
            response=client.post('/api/photos/'+photo['id']+'/export',json={'hdr':True,'dest_dir':str(dest)})
        data=response.json()
        assert response.status_code==422 and data['error']=='bad_destination',data
        assert snapshot()==before and not rec.writes
        results.append({'case':label,'status':response.status_code,'error':data['error'],'card_hashes_equal':True,'card_write_events':0})
assert audit.network_attempts()==[]
(OUT/'export_path_cases.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
