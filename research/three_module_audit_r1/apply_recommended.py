#!/usr/bin/env python3
"""Return module data with the audited short names. This module never builds or writes."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import zlib

HERE = Path(__file__).resolve().parent

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def apply(modules):
    """Accept the existing packer's three-module model and return a separate copy."""
    manifest = json.loads((HERE/'local/recommended/manifest.json').read_text())
    if tuple(m['name'] for m in modules) != ('jlaunch','qlaunch','l08firm'):
        raise ValueError('module order differs from audited data')
    result = copy.deepcopy(modules)
    for before,after,unit in zip(modules,result,manifest['modules']):
        if sha(before['map']) != unit['baseline_map_sha256']:
            raise ValueError('module map differs from audited data')
        for item in unit['records']:
            slot=item['slot']
            if (sha(before['entries'][slot]) != item['baseline_entry_sha256'] or
                    sha(before['records'][slot-1]) != item['baseline_record_sha256']):
                raise ValueError(f'{unit["name"]} slot {slot}: baseline differs from gen 117')
            record=(HERE/item['record_file']).read_bytes()
            entry=(HERE/item['entry_file']).read_bytes()
            if sha(record)!=item['record_sha256'] or sha(entry)!=item['entry_sha256']:
                raise ValueError('prepared data hash mismatch')
            identity=record[2:3]+record[4:36]+record[3:4]+record[36:51]
            if struct.unpack_from('>I',record,60)[0] != zlib.crc32(record[:60])&0xffffffff:
                raise ValueError('record CRC mismatch')
            if struct.unpack_from('>I',entry,4)[0] != zlib.crc32(identity)&0xffffffff:
                raise ValueError('entry identity mismatch')
            if entry[:4]!=before['entries'][slot][:4] or entry[8:]!=before['entries'][slot][8:]:
                raise ValueError('colour data differs from baseline')
            after['records'][slot-1]=record
            after['entries'][slot]=entry
    return result
