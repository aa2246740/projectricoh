#!/usr/bin/env python3
"""Count the actual linked sections, including a failed strict-link map."""
import json
from pathlib import Path
import re
HERE=Path(__file__).resolve().parent
def census(path):
    text=path.read_text().split('.payload ',1)[1].split('__resident_code_end',1)[0]
    result={}
    for amount,obj in re.findall(r'^\s+(?:\.\S+\s+)?0x[0-9a-f]+\s+(0x[0-9a-f]+)\s+(\S+\.o)\s*$',text,re.M):
        name=Path(obj).name;result[name]=result.get(name,0)+int(amount,16)
    return result
if __name__=='__main__':
    report=dict(premise='Header-first dynamic allocation must preserve full session bounds and leave 300 bytes.',
                observed=census(HERE/'local/build/resident.map'))
    (HERE/'local/size-census.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
