"""Check public deliverables against serials found in private source metadata."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
import re


def serials(value,active=False):
    found=set()
    if isinstance(value,dict):
        for key,item in value.items():found|=serials(item,active or 'serial' in key.lower())
    elif isinstance(value,list):
        for item in value:found|=serials(item,active)
    elif active and isinstance(value,(str,int)):
        text=str(value).strip()
        if re.fullmatch(r'[A-Za-z0-9]{7,32}',text):found.add(text)
    return found


def main():
    known=set()
    paths=[rt.ROOT/'research/gr4_dense_returns_r1/local/verified_facts.json']
    paths+=list((rt.ROOT/'research/gr_webpairs/local/samples').glob('*.json'))
    paths+=list((rt.ROOT/'research/gr4_dense_returns_r1/local/natural').glob('*.json'))
    for path in paths:known|=serials(rt.read(path))
    matches=[];public=[]
    for path in rt.HERE.iterdir():
        if not path.is_file():continue
        public.append(path.name);text=path.read_text()
        if any(value in text for value in known):matches.append(path.name)
    rt.dump('verification/privacy.json',dict(known_private_serial_count=len(known),checked_public_files=public,
                      serial_matches=matches,serial_values_published=False))
    assert not matches,matches
    print('public serial scan passed;',len(known),'private identifiers checked without printing values')


if __name__=='__main__':main()
