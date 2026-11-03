#!/usr/bin/env python3
"""Collect deterministic windows and bounded caller census from official bytes."""
from pathlib import Path
import json
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence as e

WINDOWS={r['label']:(int(r['start'],0),int(r['end'],0))
         for r in json.loads((HERE/'windows.json').read_text())}

def collect():
    e.preflight()
    im=e.Image()
    rows=[im.dump(start,end,label) for label,(start,end) in WINDOWS.items()]
    e.save('windows.json',rows)
    table=[]
    for event in range(11):
        va=0x201427b4+12*event
        table.append(dict(event=event,vma=hex(va),file=hex(im.off(va,12)),
            handlers=[hex(n) for n in struct.unpack('>3I',im.raw(va,12))]))
    e.save('dispatch.json',table)
    anchors={
      'queue2_create':0x20109a04,'task8_entry':0x2010ddc4,
      'receive_wrapper':0x20109b28,'candidate_private_dispatch_hook':0x2010de28,
      'native_classifier':0x2010e094,'native_dispatch_call':0x2010de9c,
      'native_state_publish':0x2010dea0,'native_post_handler':0x2010dea4,
      'native_table':0x201427b4,'photo_handler':0x2010e5c8,
      'photo_handler_return':0x2010e90c,'member_writer':0x2010eb0c,
      'member_dcf_tail':0x2010efbc,'member_return':0x2010efe8,
      'task28_completion_receiver':0x20173280,'task28_pair_forward':0x20173864,
      'task28_forward_to_main':0x20171674,'format_submit':0x2010a3c4,
      'format_handler':0x20111810,'module_cleanup':0x2010d70c,
      'high_open':0x200a40b4,'high_buffered_write':0x200a45e8,
      'high_direct_write':0x200a479c,'native_direct_write':0x200ac020,
      'high_close':0x200a437c,'low_close':0x200a6750,
      'slot_allocate':0x200b92f4,'slot_release':0x200b8f88,
      'generic_send':0x2010ac50,'rtos_send':0x2005e034,
    }
    e.save('anchors.json',{name:dict(vma=hex(va),file=hex(im.off(va,4)),
        instruction4_sha256=__import__('hashlib').sha256(im.raw(va,4)).hexdigest())
        for name,va in anchors.items()})
    print(json.dumps(dict(windows=len(rows),dispatch=table),indent=2))

if __name__=='__main__':
    collect()
