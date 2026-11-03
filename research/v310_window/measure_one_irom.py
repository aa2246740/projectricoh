#!/usr/bin/python3
"""Measure a card plus one IROM source, without changing the default candidate."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('window_measure',HERE/'measure.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
original=M.prepare


def prepare(name,cuts):
    source=original(name,cuts)
    path=source/'loader.c';text=path.read_text()
    text=text.replace('static const char sources[3][17]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};',
                      'static const char sources[2][17]={"/IROM/GXRCE0.DAT","/ATA1/GXRCE.DAT"};')
    text=text.replace('sources[source]','sources[source>>1]')
    text=text.replace('    status=rv_native_open(sources[2],0);\n'
                      '    if(status<0)status=rv_native_open(sources[0],0);\n'
                      '    if(status<0)status=rv_native_open(sources[1],0);',
                      '    status=rv_native_open(sources[1],0);\n'
                      '    if(status<0)status=rv_native_open(sources[0],0);')
    start=text.index('static int32_t rv_choose(');end=text.index('static int entry(',start)
    text=text[:start]+text[end:]
    text=text.replace('for(j=0;j<3;++j){','for(j=0;j<2;++j){')
    text=text.replace('if(j==1)for(i=0;i<2;++i){status=probe(r,i,trust,&c[i],w);if(status==RV_STALE)goto fail;}',
                      'if(j==1){status=probe(r,0,trust,&c[0],w);if(status==RV_STALE)goto fail;}')
    text=text.replace('chosen=j?rv_choose(c):2;','chosen=j?(c[0].valid?0:-1):2;')
    assert '/IROM/GXRCE1.DAT' not in text
    path.write_text(text)
    return source


if __name__=='__main__':
    M.prepare=prepare
    script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    definitions=[('one_irom_only',[],[]),('one_irom_combined',['roots','wordcold','aligned'],
                                       ['-flto','-fno-guess-branch-probability'])]
    results=[]
    for name,cuts,flags in definitions:
        cuts=cuts+['one_irom','script_sha256_'+script_hash]
        with contextlib.redirect_stdout(io.StringIO()):result=M.build(name,cuts,flags)
        results.append(result)
        print(json.dumps({k:result.get(k)for k in ['name','code_bytes','free_above_margin','link_ok','error']}),flush=True)
    (HERE/'one-irom-measurements.json').write_text(json.dumps(results,indent=2)+'\n')
