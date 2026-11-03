"""Recheck the independent binding cases against the separate B library."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, enable, load

def main():
    enable()
    os.environ.update(GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT='1')
    sys.path.insert(0,str(ROOT/'tools/speedlab/harness_c_next'))
    import new_cases
    def modules():
        reference=load(ROOT/'tools/native_harness/python_backend.py','b_binding_reference')
        candidate=load(ROOT/'tools/speedlab/harness_c_next/python_backend.py','b_binding_candidate')
        reference.CACHE=candidate.CACHE=HERE/'local/b-binding-decode'
        return reference,candidate
    new_cases.modules=modules
    new_cases.HERE=HERE/'local/b-binding'
    new_cases.main()

if __name__=='__main__':main()
