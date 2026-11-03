"""Compare raw original function spans, preserving attributes and whitespace."""
from pathlib import Path
import hashlib
import json
import re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
REL=Path('candidate/containers/product/src/firmware/engine/core/eng_core.c')
old=(ROOT/'firmware/engine_v45_verify'/REL).read_text();new=(ROOT/'firmware/engine_v46_ui'/REL).read_text()
NAMES='deep apply_impl rpc t_read t_store write_word recover_confirmed make_plan settings_match validate_live rebind_impl eng_require_recheck'.split()
def extract(text,name):
    matches=list(re.finditer(r'^(?:static )?(?:int|void|EngStatus)\s+'+name+r'\([^;{}]*\)\s*\{',text,re.M))
    assert len(matches)==1,(name,len(matches))
    m=matches[0];at=text.index('{',m.start());end=at+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[m.start():end].encode(),text.count('\n',0,m.start())+1
rows=[]
for name in NAMES:
    a,la=extract(old,name);b,lb=extract(new,name);assert a==b,name
    rows.append(dict(function=name,gen123_line=la,gen124_line=lb,bytes=len(b),
                     sha256=hashlib.sha256(b).hexdigest(),byte_exact=True))
(OUT/'evidence/critical-12-exact.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS 12 exact original source spans, without stripping attributes or whitespace')
