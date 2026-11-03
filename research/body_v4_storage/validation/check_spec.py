#!/usr/bin/env python3
"""Check the diagnostic specification, not a diagnostic implementation."""
import json
from pathlib import Path
import string
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as v

def main():
    v.preflight()
    spec=json.loads((v.HERE/"diagnostic_spec.json").read_text())
    image=v.Image()
    spans=[(s["vma"],s["vma"]+s["size"]) for s in image.sections]
    spans += [(s["bss"],s["bss"]+s["bss_size"]) for s in image.sections]
    values={"seq":0xffff,"quality":"CHANGE"}
    for name,(address,width) in spec["fields"].items():
        a=int(address,0)
        assert width in (1,2,4) and a % width == 0
        assert 0x20000000 <= a < a+width <= 0x20800000
        assert any(lo <= a and a+width <= hi for lo,hi in spans),name
        values[name]=(1 << (8*width))-1
    result=[]
    fmt=string.Formatter()
    for name,rows in spec["views"].items():
        assert len(rows)==8,name
        for row in rows:
            for _,field,_,_ in fmt.parse(row):
                assert field is None or field in values,(name,field)
            rendered=row.format(**values)
            assert rendered.isascii() and len(rendered)<=spec["max_ascii_columns"],(name,rendered)
        result.append(dict(view=name,rows=8,max_columns=max(len(x.format(**values)) for x in rows)))
    v.save("diagnostic-spec-check.json",dict(status="PASS_SPEC_ONLY",views=result,fields=len(spec["fields"]),
         limits="No DAT exists. No compiled call graph, native UI execution or camera rendering has been verified."))
    print(json.dumps(dict(status="PASS_SPEC_ONLY",views=len(result),fields=len(spec["fields"]))))

if __name__=="__main__":
    main()
