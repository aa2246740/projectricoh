"""Summarize the three completed old-entry model sessions."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
PIN='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'

def main():
    units={};fixture_hashes=set()
    for unit in ('50mm','28mm','mount'):
        path=WORK/'local'/('old-entry-model-'+unit)/'review_g126'/('old-entry-model-'+unit+'.json')
        data=json.loads(path.read_text())
        assert data['status']=='PASS' and data['unit']==unit and data['records']==32
        assert data['final_dat_sha256']==PIN and data['code_byte_equal'] and data['initialization_visits']>=1
        fixture_hashes.add(data['fixture_sha256'])
        units[unit]={'records':32,'initialization_visits':data['initialization_visits'],
                     'source':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    assert len(fixture_hashes)==1
    result={'status':'PASS','final_dat_sha256':PIN,'fixture_sha256':fixture_hashes.pop(),
            'records':96,'units':units,'scope':'Synthetic data with the exact final code; fresh M32R sessions.'}
    (WORK/'legacy-model-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'name':'old_entry_model_summary','returncode':0,'units':3,'records':96}))

if __name__=='__main__':main()
