#!/usr/bin/python3
"""Rebuild the unchanged resident with the original strict linker script."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1/resident-link')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    path=ROOT/'research/g155/build_resident.py'
    tree=ast.parse(path.read_text(),filename=str(path))
    # Remove only the final publication copy. Compilation and identity stay intact.
    build=next(v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name=='build')
    publications=[v for v in build.body if isinstance(v,ast.If) and any(
        isinstance(n,ast.Name) and n.id=='canonical' for n in ast.walk(v))]
    assert len(publications)==1
    build.body.remove(publications[0])
    module=types.ModuleType('review_resident_builder');module.__file__=str(path)
    exec(compile(tree,str(path),'exec'),module.__dict__)
    module.HERE=HERE/'local/resident-link';module.TEMP=TEMP
    os.environ['TMPDIR']=str(TEMP)
    module.preflight()
    size=module.build('neutral')
    actual=(module.HERE/'evidence/resident/neutral/resident.bin').read_bytes()
    expected=(ROOT/'firmware/resident_v310_g155/local/resident/resident.bin').read_bytes()
    assert actual==expected
    assert size['link_ok'] and size['code_bytes']==7968 and size['free_above_margin']==92
    receipt=dict(status='PASS',resident_sha256=hashlib.sha256(actual).hexdigest(),
        byte_equal=True,code_bytes=size['code_bytes'],free_above_margin=size['free_above_margin'],
        compiler_source=str(path.relative_to(ROOT)),compiler_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        original_linker_script=True,publication_copy_omitted=True,
        outputs='local/resident-link/evidence/resident/neutral',measurement=size)
    target=HERE/'evidence/strict-link.json';assert not target.exists()
    target.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('status','resident_sha256','code_bytes','free_above_margin')}))


if __name__=='__main__':main()
