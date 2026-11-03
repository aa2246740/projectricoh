#!/usr/bin/python3
"""Run the review drivers on the original batch runtime, with explicit models."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def main():
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--kind',choices=('cold','recovery'),required=True)
    a,remaining=p.parse_known_args()
    tool=ROOT/'tools'/('gxr_emulator_standby' if a.kind=='cold' else 'gxr_emulator_batch')
    sys.path.insert(0,str(tool))
    import storage_run
    original=storage_run.Backend
    names=['nand-word','sd-long-response']
    if a.kind=='cold':names=['nand-word','preview-link','sd-long-response','nand-read-tail']
    configuration=[]
    for name in names:
        path=ROOT/'research/v310_body/fix/emulator'/(name.replace('-','_')+'.py')
        module=load('review_batch_'+name.replace('-','_'),path);module.install()
        configuration.append(dict(name=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    class ReviewBatchBackend(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.model_revision=configuration
            self.library_path=tool/'build/libgxr_m32r.dylib'
            self._observer_owners=[]
            self._native_driver=None
        def materialize_native(self):
            return None
        def add_write_trace(self,lo,hi,callback,native=None):
            return super().add_write_trace(lo,hi,callback)
    storage_run.Backend=ReviewBatchBackend
    script=HERE/('cold.py' if a.kind=='cold' else 'recovery_tail.py')
    source=script.read_text()
    old="str(ROOT/'tools/gxr_emulator_fast')"
    assert source.count(old)==1
    source=source.replace(old,'str('+repr(str(tool))+')')
    runner=types.ModuleType('review_batch_driver');runner.__file__=str(script)
    sys.modules[runner.__name__]=runner
    exec(compile(source,str(script),'exec'),runner.__dict__)
    sys.argv=[str(script),*remaining]
    name=remaining[remaining.index('--name')+1]
    target=HERE/'evidence'/(name+'.json')
    print(json.dumps(dict(name=name,runtime_tool=str(tool.relative_to(ROOT)),models=names)),flush=True)
    try:runner.main()
    finally:
        if target.exists():
            data=json.loads(target.read_text())
            data.update(runtime_tool=str(tool.relative_to(ROOT)),backend='original-batch',
                        actual_backend_module=str(sys.modules['backend'].__file__),
                        native_machine_used=False,adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        driver_import_path_rebound=True,
                        model_configuration=configuration,
                        adapter_role='Metadata and optional callback-argument compatibility; original callbacks and scheduler execute')
            target.write_text(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':main()
