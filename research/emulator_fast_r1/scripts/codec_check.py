"""C transport and canonical digest versus their Python definitions."""
from collections import Counter,deque
import json,os,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST
enable();sys.path.insert(0,str(FAST))
os.environ['GXR_FAST_MODEL_FIXES']='preview-link'
import models
models.configure()
import unit_link,wire,snapshots as S


def main():
    rng=random.Random(731)
    cases=[None,True,False,0,-1,1<<65,-(1<<128),1<<16384,'中文\0λ',b'\0\xff',bytearray(b'ab'),Counter(a=3,b=0),deque([1,2],maxlen=7),set(),frozenset({1,2}),unit_link.UnitLink('50mm')]
    def value(depth=0):
        kind=rng.randrange(11 if depth<3 else 6)
        if kind==0:return None
        if kind==1:return bool(rng.randrange(2))
        if kind==2:return rng.randrange(-(1<<rng.randrange(1,900)),1<<rng.randrange(1,900))
        if kind==3:return ''.join(rng.choice('a中\0λ') for _ in range(rng.randrange(20)))
        if kind==4:return bytes(rng.randrange(256) for _ in range(rng.randrange(20)))
        if kind==5:return bytearray(rng.randrange(256) for _ in range(rng.randrange(20)))
        if kind==6:return [value(depth+1) for _ in range(rng.randrange(5))]
        if kind==7:return tuple(value(depth+1) for _ in range(rng.randrange(5)))
        if kind==8:return {str(i):value(depth+1) for i in range(rng.randrange(5))}
        if kind==9:return deque([value(depth+1) for _ in range(3)],maxlen=7)
        return frozenset(rng.randrange(20) for _ in range(4))
    cases += [value() for _ in range(500)]
    for item in cases:
        assert S.hash_value(item)==S.hash_value_reference(item)
        opaque={};native=wire.encode(item,opaque,S.function_key);reference=wire.encode_reference(item,{},S.function_key)
        assert native==reference
        assert S.hash_value(wire.decode(native,opaque))==S.hash_value(item)
        assert S.hash_value(wire.decode_reference(native,opaque))==S.hash_value(item)
    result=dict(status='passed',cases=len(cases),canonical_python_equivalent=True,wire_c_python_equivalent=True,preview_link=True,seed=731)
    (HERE/'runs/codec-final9.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
