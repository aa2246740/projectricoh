"""Exercise the API gate using the archived real API-3 extension."""
import importlib.util
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, load, sha

def main():
    enable()
    adapter=load(ROOT/'tools/native_harness_c/ccore/backend.py','review_api_adapter')
    old=ROOT/'research/speed_hillclimb/local/review_fix/pre_fix/_gxr_ccore.cpython-39-darwin.so'
    assert sha(old)=='15f9b4e4cc28ff727d56f269ef57f7b938bb115485cd528996761158922b072f'
    spec=importlib.util.spec_from_file_location('_gxr_ccore',old)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.API_VERSION==3
    record=json.loads((ROOT/'tools/native_harness_c/local/ccore/build.json').read_text())
    record.update(library=str(old),sha256=sha(old))
    local_manifest=HERE/'local/old-api-manifest.json'
    emit(local_manifest,record)
    os.environ['GXR_CCORE_BUILD_MANIFEST']=str(local_manifest)
    try:
        adapter.load_native()
    except RuntimeError as error:
        message=str(error)
    else:
        raise AssertionError('old API accepted')
    assert message=='C core API differs',message
    os.environ.pop('GXR_CCORE_BUILD_MANIFEST')
    current=adapter.load_native()
    assert current.API_VERSION==4
    emit(HERE/'local/api-summary.json',dict(passed=True,old_library_sha256=sha(old),old_api=module.API_VERSION,
         old_rejection=message,current_api=current.API_VERSION,
         current_library_sha256=record['sources'] and sha(ROOT/'tools/native_harness_c/local/ccore/_gxr_ccore.cpython-39-darwin.so'),
         note='Current source identities and ABI pass before the real archived API-3 library is rejected.'))
    print(json.dumps(dict(passed=True,old_api=module.API_VERSION,rejection=message,current_api=current.API_VERSION)),flush=True)

if __name__=='__main__':main()
