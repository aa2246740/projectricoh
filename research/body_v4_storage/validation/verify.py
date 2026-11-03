#!/usr/bin/env python3
"""Sequential checks in one Python process, with retained per-step output."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import validate as v

def load(name):
    spec=importlib.util.spec_from_file_location("validation_"+name,HERE/(name+".py"))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def full():
    v.preflight()
    steps=[("collect",v.collect),("scan",load("scan").main),("replay",load("replay").main),
           ("sizing",load("sizing").main),("summarize",load("summarize").main),
           ("diagnostic_spec",load("check_spec").main),("protected_inputs",v.after)]
    records=[]
    for i,(name,f) in enumerate(steps,1):
        output,error=io.StringIO(),io.StringIO()
        failed=None
        try:
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(error):
                f()
        except Exception:
            failed=traceback.format_exc()
            error.write(failed)
        (v.OUT/("final-"+str(i)+"-"+name+".stdout")).write_text(output.getvalue())
        (v.OUT/("final-"+str(i)+"-"+name+".stderr")).write_text(error.getvalue())
        records.append(dict(step=name,status="FAIL" if failed else "PASS"))
        if failed:
            v.save("final-checks.json",dict(status="FAIL",steps=records))
            raise RuntimeError(name+" failed; see retained stderr")
        print("PASS "+name)
    report=(HERE/"VALIDATION.md").read_text()
    for label,target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)",report):
        assert not target.startswith(("http:","https:","file:"))
        assert (HERE/target.split("#",1)[0]).is_file(),(label,target)
    for i in range(1,11):
        assert re.search(r"^## V"+str(i)+r"\.",report,re.M),i
    assert report.splitlines()[0].startswith("仍不可行：")
    records.append(dict(step="report_links_and_V1_to_V10",status="PASS"))
    v.save("final-checks.json",dict(status="PASS_STATIC_HOST_AND_SPEC_ONLY",steps=records,
        device="NOT_RUN",product_mutations=False,image_or_DAT_generated=False,
        limits="Checks cover named static windows, synthetic host fixtures and specification shape only."))
    print("PASS_STATIC_HOST_AND_SPEC_ONLY")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("action",choices=("full",))
    ap.parse_args()
    full()

if __name__=="__main__":
    main()
