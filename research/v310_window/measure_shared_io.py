#!/usr/bin/python3
"""Share the two identical file-state checks, preserving their call order."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('one_irom_measure',HERE/'measure_one_irom.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
original=S.M.prepare


def prepare(name,cuts):
    source=S.prepare(name,cuts) if 'one_irom' in cuts else original(name,cuts)
    p=source/'loader.c';text=p.read_text()
    condition='!unchanged(r,epochs)||(source==2&&(rv_native_sd_id(now)||!rv_equal(id,now,16)))'
    assert text.count(condition)==2
    text=text.replace(condition,'!read_stable(r,source,w)')
    text=text.replace(',*now=w->now','')
    helper=('static __attribute__((noinline)) int read_stable(RvRoot *r,unsigned source,RvLoadWork *w)\n'
            '{return unchanged(r,w->read_epochs)&&\n'
            '    !(source==2&&(rv_native_sd_id(w->now)||!rv_equal(w->id,w->now,16)));}\n')
    at=text.index('static int32_t read_one(')
    text=text[:at]+helper+text[at:]
    p.write_text(text)
    return source


if __name__=='__main__':
    S.M.prepare=prepare
    hashes=['parent_sha256_'+hashlib.sha256((HERE/'measure_one_irom.py').read_bytes()).hexdigest(),
            'script_sha256_'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()]
    base=['roots','wordcold','aligned','shared_io',*hashes]
    definitions=[('neutral_shared_io',base,[]),('one_irom_shared_io',base+['one_irom'],[]),
                 ('one_irom_shared_io_sra',base+['one_irom'],['-fno-ipa-sra'])]
    results=[]
    for name,cuts,extra in definitions:
        with contextlib.redirect_stdout(io.StringIO()):
            result=S.M.build(name,cuts,['-flto','-fno-guess-branch-probability',*extra])
        results.append(result)
        print(json.dumps({k:result.get(k)for k in ['name','code_bytes','free_above_margin','link_ok','error']}),flush=True)
    (HERE/'shared-io-measurements.json').write_text(json.dumps(results,indent=2)+'\n')
