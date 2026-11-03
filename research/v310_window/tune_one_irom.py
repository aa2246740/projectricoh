#!/usr/bin/python3
"""Measure small compiler alternatives for the one-IROM-source candidate."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('one_irom_measure',HERE/'measure_one_irom.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


if __name__=='__main__':
    S.M.prepare=S.prepare
    cuts=['roots','wordcold','aligned','one_irom',
          'parent_sha256_'+hashlib.sha256((HERE/'measure_one_irom.py').read_bytes()).hexdigest(),
          'script_sha256_'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()]
    flags=['-fno-ipa-sra','-fno-tree-coalesce-vars','-fno-caller-saves','-fno-inline-functions-called-once',
           '-fno-tree-dominator-opts','-fno-expensive-optimizations','-fno-forward-propagate','-fno-schedule-insns2']
    results=[]
    for i,flag in enumerate(flags):
        with contextlib.redirect_stdout(io.StringIO()):
            result=S.M.build('one_irom_tune_'+str(i).zfill(2),cuts,['-flto','-fno-guess-branch-probability',flag])
        results.append(result)
        print(json.dumps({k:result.get(k)for k in ['name','code_bytes','free_above_margin','link_ok']}),flush=True)
    (HERE/'one-irom-tuning.json').write_text(json.dumps(results,indent=2)+'\n')
