"""Read-only vocabulary check for final report, scripts, names and text records."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from neutral_terms import OUT,pattern
from common import save
bad=[];count=0
for p in OUT.rglob('*'):
    if pattern.search(p.name):bad.append(dict(path_hex=str(p.relative_to(OUT)).encode().hex(),kind='name'))
    if p.is_file():
        try:s=p.read_text()
        except (UnicodeDecodeError,ValueError):continue
        count+=1
        if pattern.search(s):bad.append(dict(path_hex=str(p.relative_to(OUT)).encode().hex(),kind='text'))
save('neutral-terms-check.json',dict(text_files=count,failures=bad,ok=not bad))
assert not bad,'Vocabulary check failed; see encoded path records.'
print('PASS neutral vocabulary',count,'text files',flush=True)
