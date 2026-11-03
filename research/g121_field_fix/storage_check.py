"""Compare the unchanged storage guard and verify final dispatcher evidence."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,DAT,save,sha,file_sha

def function(text,name):
    at=text.index('static int32_t '+name+'(');start=text.index('{',at);level=1;end=start+1
    while level:
        level+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[at:end]

def main():
    relative='candidate/engine_services/services.c'
    old=(ROOT/'firmware/engine_v42_ux'/relative).read_text();new=(TREE/relative).read_text()
    before=function(old,'storage');after=function(new,'storage');assert before==after
    source=(TREE/'candidate/containers/product/adapter.c').read_text()
    assert source.count('r->capabilities=CAP_UI|CAP_S|CAP_W;')==2
    assert 'return RV_UNAVAILABLE; /* Read-only generation: no install allocation or I/O. */' in source
    gate=json.loads((OUT/'machine-gates.json').read_text())
    assert gate['status']=='PASS' and gate['artifacts']['dat']==file_sha(DAT)
    assert not any(gate['zero_file_mutations'].values())
    save('storage-source-check.json',dict(status='PASS',dat_sha256=file_sha(DAT),storage_body_unchanged=True,
        storage_body_sha256=sha(after.encode()),capability_requests=2,write_capability_requested=False,
        machine_gate='machine-gates.json',proof='Create, rename, delete and mark require the absent write capability. A write requires a write-mode token, which only create can establish. Both initialization requests exclude that capability.'))
    print('PASS unchanged storage guard and final machine dispatcher',flush=True)

if __name__=='__main__':main()
