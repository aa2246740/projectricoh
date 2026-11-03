#!/usr/bin/python3
"""Check the spare column using an official data page and an erased spare area."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/gxr_emulator_batch'))
spec=importlib.util.spec_from_file_location('v310_word_nand',HERE/'emulator/nand_word.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)


def address(device,column,row):
    for value in column.to_bytes(2,'little')+row.to_bytes(2,'little'):
        device.write(0x8000,bytes([value]))


def main():
    source=ROOT/'artifacts/firmware/gxr-1.51/ilaunch0'
    data=source.read_bytes()[0x80200:0x80a00]
    assert len(data)==2048 and data[1024:1026]!=b'\xff\xff'
    page=data+bytes([255])*64
    rows=[]
    for cls in (model.OriginalNAND,model.WordColumnNAND):
        device=cls();device.pages[192]=page
        device.write(0x10000,b'\0');address(device,1024,192);device.write(0x10000,b'\x30')
        marker=device.read(0,2)
        if cls is model.WordColumnNAND:assert marker==b'\xff\xff'
        else:assert marker==data[1024:1026]
        device.write(0x10000,b'\x80');address(device,1024,192)
        device.write(0,b'\0\0');device.write(0x10000,b'\x10')
        correct=device.pages[192][:2048]==data and device.pages[192][2048:2050]==b'\0\0'
        assert correct==(cls is model.WordColumnNAND)
        rows.append(dict(model=cls.__name__,marker_is_erased=marker==b'\xff\xff',
                         data_untouched_and_marker_written=correct))
    result=dict(source=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        data_range=['0x80200','0x80a00'],data_sha256=hashlib.sha256(data).hexdigest(),
        declared_storage_input=True,native_state_presets=[],results=rows,
        conclusion='Original byte-column model reads and writes data at the native spare column; halfword columns preserve data')
    (HERE/'evidence/nand-column-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
