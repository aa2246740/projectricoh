"""Run retained instruction and audit gates against the exact release candidate."""
import argparse,importlib.util,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable
sys.path.insert(0,str(ROOT/'tools/speedlab'))
import differential_fix2 as differential
from common import load
LOCAL=Path(os.environ.get('GXR_GATE_OUTPUT',str(HERE/'local/gates')))
def modules():
    sys.path.insert(0,str(ROOT/'tools/speedlab/harness_release'))
    reference=load(ROOT/'tools/native_harness/python_backend.py','release_reference')
    os.environ['GXR_HARNESS_BACKEND']='c'
    candidate=load(ROOT/'tools/speedlab/harness_release/python_backend.py','release_candidate')
    reference.CACHE=candidate.CACHE=LOCAL/'decode'
    return reference,candidate
if __name__=='__main__':
    kind=sys.argv.pop(1)
    differential.modules=modules;differential.enable=enable;differential.LOCAL=LOCAL
    if kind=='differential':raise SystemExit(differential.main())
    if kind=='audit':
        import audit_checks as check
        check.enable=enable;check.modules=modules;check.LOCAL=LOCAL
        raise SystemExit(check.main())
    raise ValueError('unknown gate')
