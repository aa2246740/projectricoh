"""Prepare isolated outputs and reuse byte-checked decoder cache files."""
from pathlib import Path
import json
import runpy
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,ENGINE,enable,check_inputs

def main():
    enable();check_inputs()
    sys.path.insert(0,str(ROOT/'tools/native_harness'))
    canonical=runpy.run_path(str(ROOT/'tools/native_harness/python_backend.py'))['PythonBackend']
    retained=runpy.run_path(str(ROOT/'firmware/engine_v48_own/native_harness/python_backend.py'))['PythonBackend']
    assert canonical._decode.__code__.co_code==retained._decode.__code__.co_code
    assert canonical._decode.__code__.co_names==retained._decode.__code__.co_names
    canonical_cache=WORK/'local/target/decode'
    caches=[path for root in (ENGINE,WORK/'local') for path in root.rglob('decode')
            if path.is_dir() and path!=canonical_cache and 'local' in path.parts]
    assert caches,'a populated retained decoder cache is required'
    count=0
    sources={}
    for root in (WORK/'local/target/decode',WORK/'local/release129/review_g126/local/decode'):
        for source in root.rglob('*'):
            if source.is_file() and source.suffix in ('.bin','.txt'):
                if source.name in sources:
                    if source.suffix=='.bin':assert sources[source.name].read_bytes()==source.read_bytes()
                else:sources[source.name]=source
    for unit in ('28mm','mount'):
        for kind in ('ownership-settings','cold-reentry'):
            cache=WORK/'local'/('release129-'+unit)/'review_g126/local/decode'/('129-'+unit+'-'+kind)
            cache.mkdir(parents=True,exist_ok=True);caches.append(cache)
    for cache in caches:
        for source in sources.values():
            if not source.is_file():continue
            target=cache/source.name
            if target.exists():
                if source.suffix=='.bin':assert target.read_bytes()==source.read_bytes()
            else:shutil.copyfile(source,target);count+=1
    original=WORK/'local/release129/review_g126/local/layout'
    for unit in ('28mm','mount'):
        output=WORK/'local'/('release129-'+unit)/'review_g126/local/layout'
        output.mkdir(parents=True,exist_ok=True)
        for source in original.iterdir():
            if source.is_file():shutil.copyfile(source,output/source.name)
    print(json.dumps({'name':'prepare_two_units','returncode':0,'decoder_caches':len(caches),'cache_files_added':count}))

if __name__=='__main__':main()
