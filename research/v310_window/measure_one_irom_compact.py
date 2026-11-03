#!/usr/bin/python3
"""Use two private candidate slots while preserving public source ids 1 and 3."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('one_irom_measure',HERE/'measure_one_irom.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


def prepare(name,cuts):
    source=S.prepare(name,cuts)
    p=source/'loader.c';text=p.read_text()
    edits=[('RvCandidate candidates[3]','RvCandidate candidates[2]'),
           ('sources[source>>1]','sources[source]'),('source==2','source==1'),
           ('chosen=2,status','chosen=1,status'),
           ('probe(r,2,trust,&c[2],w)','probe(r,1,trust,&c[1],w)'),
           ('chosen=j?(c[0].valid?0:-1):2','chosen=j?(c[0].valid?0:-1):1'),
           ('chosen==2','chosen==1'),('s->selected_source=chosen+1','s->selected_source=chosen?3:1')]
    for old,new in edits:
        assert old in text,old
        text=text.replace(old,new)
    p.write_text(text)
    return source


if __name__=='__main__':
    S.M.prepare=prepare
    hashes=['parent_sha256_'+hashlib.sha256((HERE/'measure_one_irom.py').read_bytes()).hexdigest(),
            'script_sha256_'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()]
    cuts=['roots','wordcold','aligned','one_irom_compact',*hashes]
    results=[]
    for name,extra in [('one_irom_compact',[]),('one_irom_compact_sra',['-fno-ipa-sra'])]:
        with contextlib.redirect_stdout(io.StringIO()):
            result=S.M.build(name,cuts,['-flto','-fno-guess-branch-probability',*extra])
        results.append(result)
        print(json.dumps({k:result.get(k)for k in ['name','code_bytes','free_above_margin','link_ok','error']}),flush=True)
    (HERE/'one-irom-compact.json').write_text(json.dumps(results,indent=2)+'\n')
