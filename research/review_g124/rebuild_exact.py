"""Rebuild all services, product code and packed data only under review local/."""
from pathlib import Path
import difflib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

def main():
    folder=OUT/'local/rebuild';routing=folder/'routing'
    routing.mkdir(parents=True,exist_ok=True)
    candidate=TREE/'candidate'
    c=load(candidate/'common.py','common')
    c.LOCAL=folder
    def save_scoped(path,value):
        path=Path(path);assert path.resolve().is_relative_to(OUT)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
    c.save=save_scoped
    patches=[]
    service_source=(candidate/'service_build.py').read_text()
    adjusted=service_source.replace('archive.relative_to(c.HERE)','archive.relative_to(c.ROOT)').replace('elf.relative_to(c.HERE)','elf.relative_to(c.ROOT)')
    service_path=routing/'service_build.py';service_path.write_text(adjusted)
    patches.extend(difflib.unified_diff(service_source.splitlines(True),adjusted.splitlines(True),fromfile='original/service_build.py',tofile='review/local/service_build.py'))
    load(service_path,'service_build')
    # Keep every source, include and compiler flag at its original path.
    # Only the archive input and producer output/log directories are routed.
    sys.path.insert(0,str(candidate/'containers/product'))
    runtime=load(candidate/'containers/product/runtime.py','runtime')
    runtime._common.LOCAL=folder
    runtime._common.save=save_scoped
    runtime.LOCAL=folder/'product-r13'
    product_source=(candidate/'containers/product/build.py').read_text()
    adjusted=product_source.replace("HERE.parents[1]/'local/resident/engine-services/libgxr_services.a'",
        repr(str(folder/'resident/engine-services/libgxr_services.a')))
    product_path=routing/'product_build.py';product_path.write_text(adjusted)
    patches.extend(difflib.unified_diff(product_source.splitlines(True),adjusted.splitlines(True),fromfile='original/product/build.py',tofile='review/local/product_build.py'))
    (folder/'routing.patch').write_text(''.join(patches))
    original_load=c.load
    def routed_load(path,name):
        if Path(path)==candidate/'containers/product/build.py':path=product_path
        return original_load(path,name)
    c.load=routed_load
    builder=load(candidate/'build124.py','review_exact_builder')
    sys.argv=[str(Path(__file__).resolve())]
    builder.main()
    frozen=candidate/'local/full-r13';built=folder/'full-r13'
    names=('GXRCE.DAT','engine.bin','reloc.bin','effective-rows.bin')
    equal={name:(built/name).read_bytes()==(frozen/name).read_bytes() for name in names}
    result=dict(status='PASS' if all(equal.values()) else 'FAIL',equal=equal,
        DAT_sha256=file_sha(built/'GXRCE.DAT'),published_DAT_sha256=PIN,
        services_rebuilt=True,product_rebuilt=True,data_repacked=True,
        source_and_compiler_flags_changed=False,output=str(folder.relative_to(ROOT)))
    save('evidence/rebuild-exact.json',result)
    print(json.dumps(result));assert all(equal.values()) and result['DAT_sha256']==PIN

if __name__=='__main__':main()
