"""Collect completed isolated records and seal the bounded task result."""
from pathlib import Path
import argparse
import hashlib
import json
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,enable,check_inputs

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reason',required=True);args=parser.parse_args()
    enable();check_inputs()
    final=WORK/'local/release129/review_g126'
    copied=[]
    for unit in ('28mm','mount'):
        folder=WORK/'local'/('release129-'+unit)/'review_g126'
        for source in folder.glob('*.json'):
            if source.name.endswith('-diagnostic.json'):continue
            is_cold=source.name==f'cold_reentry---generation-129---unit-{unit}.json'
            is_product=source.name in (f'product-{unit}.json',f'product-stack-{unit}.json',f'product-rpc-{unit}.json')
            if not (is_cold or is_product):continue
            value=json.loads(source.read_text())
            if is_cold and value.get('returncode')!=0:continue
            if source.name==f'product-{unit}.json' and value.get('status')!='PASS':continue
            (final/source.name).write_bytes(source.read_bytes());copied.append(source.name)
    sys.argv=[str(WORK/'finalize.py'),'--incomplete',args.reason]
    runpy.run_path(str(WORK/'finalize.py'),run_name='__main__')
    lines=(WORK/'SHA256SUMS').read_text().splitlines();count=0
    for line in lines:
        digest,name=line.split('  ',1)
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,('checksum',name)
        count+=1
    result={'status':'PASS','files':count,'copied':copied,'frozen_inputs':check_inputs()}
    print(json.dumps({'name':'final_checksum_check','returncode':0,**result}))

if __name__=='__main__':main()
