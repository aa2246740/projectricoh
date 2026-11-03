"""Measure a review-only alternative: disable every black-box file write."""
import difflib
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a
sys.path.insert(0,str(a.HERE/'isolated/candidate'))
import common as c
import build116 as candidate

def main():
    readonly='--readonly' in sys.argv
    fix=a.HERE/('minimal-fix-readonly' if readonly else 'minimal-fix');fix.mkdir(exist_ok=True)
    original=(c.PRODUCT/'blackbox.c').read_text()
    changed=original.replace('int ig_bx_flush(unsigned reason)\n{',
                            'int ig_bx_flush(unsigned reason)\n{\n    return 0; /* Review-only: no black-box media writes. */',1)
    assert changed!=original
    (fix/'blackbox.c').write_text(changed)
    (fix/'change.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='blackbox.c',tofile='blackbox.c')))
    sys.path.insert(0,str(c.PRODUCT))
    pack=c.load(c.PRODUCT/'pack.py','fix_pack')
    b=c.load(c.PRODUCT/'build.py','fix_build')
    if readonly:
        adapter=(c.PRODUCT/'adapter.c').read_text()
        assert adapter.count('CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W')==2
        (fix/'adapter.c').write_text(adapter.replace('CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W','CAP_UI|CAP_S|CAP_W'))
    original_sources=b.sources
    b.sources=lambda:[(fix/'blackbox.c' if p==c.PRODUCT/'blackbox.c' else fix/'adapter.c' if readonly and p==c.PRODUCT/'adapter.c' else p,s) for p,s in original_sources()]
    b.run=lambda argv,label: a.run(argv,('readonly-fix-' if readonly else 'fix-')+label,timeout=600,cwd=a.ROOT)
    b.LOCAL=fix/'build';b.LOCAL.mkdir(exist_ok=True)
    modules=candidate.model(pack)
    inert,_,_=pack.pack_model(modules,116)
    layout=b.build(len(inert)-256-len(pack.STUB),lto=True)
    built=b.LOCAL/'m32r-lto'
    old=json.loads((c.LOCAL/'full-r13/layout.json').read_text())
    trust=json.loads((c.UPSTREAM/'local/resident/trust.json').read_text())
    rel=(built/'reloc.bin').read_bytes()
    blob,_,_=pack.pack_model(modules,116,engine=(built/'engine.bin').read_bytes(),
        relocations=[struct.unpack_from('>II',rel,i) for i in range(0,len(rel),8)],
        bss=layout['bss_bytes'],entry=layout['entries']['ig_bootstrap'],
        resident_id=bytes.fromhex(trust['resident_build_id']),abi_id=bytes.fromhex(trust['resident_abi_id']))
    (fix/'REVIEW_ONLY_NOT_FOR_INSTALL.DAT').write_bytes(blob)
    a.dump(str(fix.relative_to(a.HERE))+'/result.json',dict(status='MEASURED_REVIEW_ONLY',bytes=len(blob),
        sha256=a.sha(fix/'REVIEW_ONLY_NOT_FOR_INSTALL.DAT'),engine_bytes=layout['engine_bytes'],
        bss_bytes=layout['bss_bytes'],file_delta=len(blob)-old['file_bytes'],
        code_delta=layout['engine_bytes']-old['engine_bytes'],bss_delta=layout['bss_bytes']-old['bss_bytes'],
        behavior_cost=('All black-box media flushes and CAP_FILE_WRITE disabled; no IROM install or GXTS/GXLS persistence; card required at each boot.' if readonly else 'All black-box media flushes disabled. RAM witnesses and recipe/GXTS/GXLS functions remain.') ))
    print((fix/'result.json').read_text())

if __name__=='__main__':main()
