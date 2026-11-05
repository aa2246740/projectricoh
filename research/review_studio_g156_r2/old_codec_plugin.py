"""For the before/after check, supply the exact r1 codec via importlib, without editing it."""
from pathlib import Path
import importlib.util
import sys

def pytest_configure(config):
    from gxr_studio.camdata import datcodec as previous
    import gxr_studio.camdata as package
    name='gxr_studio.camdata.datcodec'
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parent/'old_datcodec.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    package.datcodec=module
    for loaded in list(sys.modules.values()):
        if loaded is not None and getattr(loaded,'datcodec',None) is previous:
            loaded.datcodec=module
