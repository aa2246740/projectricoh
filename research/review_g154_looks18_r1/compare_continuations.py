"""Compare independent inherited-OPEN replays without ignoring changed state."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *

def read(unit,backend,baseline=False):
    suffix='-baseline' if baseline else ''
    return json.loads((HERE/'evidence'/f'continuation-{unit}-{backend}{suffix}.json').read_text())

def normalized(case):
    out={k:v for k,v in case.items() if k!='observations'}
    out['observations']=[]
    for old in case['observations']:
        new={k:v for k,v in old.items() if k not in ('S_sha256','frame')}
        new['frame']={k:v for k,v in old['frame'].items() if k not in ('count','labels')}
        out['observations'].append(new)
    return out

def main():
    comparisons=[]
    for unit in ('50mm','mount'):
        for baseline in (False,True):
            c=read(unit,'c',baseline);p=read(unit,'python',baseline)
            assert c['status']==p['status']=='PASS' and c['details']==p['details'],(unit,baseline,'C/Python mismatch')
            comparisons.append(dict(unit=unit,comparison='C equals Python',variant='baseline' if baseline else 'looks18',
                                    complete_observations_equal=True,includes_full_S_hash=True))
        old=read(unit,'c',True)['details']['cases'];new=read(unit,'c')['details']['cases']
        assert len(old)==len(new)==2
        for a,b in zip(old,new):
            assert normalized(a)==normalized(b),(unit,a['kind'],'baseline behavioral delta')
            assert a['behavior']==b['behavior']=='OPEN'
            comparisons.append(dict(unit=unit,comparison='baseline equals looks18',kind=a['kind'],
                                    same_navigation_and_close_behavior=True,same_unit_and_552_bytes=True,
                                    excluded_fields=['frame.count','frame.labels','S_sha256'],
                                    reason='Logical row count and labels differ by design. S carries each DAT identity; every replay separately asserts all 4096 S bytes unchanged.'))
    save('evidence/continuation-comparison.json',dict(status='PASS',comparisons=comparisons,
         conclusion='Both OPEN paths persist identically to the currently used baseline in the tested host sequences. Neither is recorded as fixed.'))
    print(json.dumps(dict(status='PASS',comparisons=len(comparisons))))

if __name__=='__main__':main()
