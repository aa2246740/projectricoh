#!/usr/bin/python3
"""Read both new DAT files with the unmodified Studio codec."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert (3,12)<=sys.version_info[:2]<=(3,14)
    source=ROOT/'studio/src/gxr_studio/camdata/datcodec.py'
    spec=importlib.util.spec_from_file_location('g155b_studio_reader',source)
    codec=importlib.util.module_from_spec(spec);sys.modules[spec.name]=codec;spec.loader.exec_module(codec)
    rows=[]
    for suffix in ('','_test'):
        path=ROOT/('firmware/package_v310_g155b'+suffix)/'GXRCE.DAT'
        raw=path.read_bytes();dat=codec.parse(raw)
        assert dat.generation==155 and codec.pack(dat)==raw
        rows.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),
            generation=dat.generation,roundtrip_equal=True,looks=len(dat.looks),users=len(dat.users),
            look_bases=[look.base for look in dat.looks],user_bases=[user['base'] for user in dat.users],
            maps=[module.map.hex() for module in dat.modules]))
    result=dict(reader=str(source.relative_to(ROOT)),reader_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        python=sys.version.split()[0],studio_changes=False,results=rows)
    (HERE/'evidence/studio-compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in row.items() if k not in ('maps','look_bases','user_bases')} for row in rows]))


if __name__=='__main__':main()
